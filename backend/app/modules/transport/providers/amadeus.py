from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx
from pydantic import SecretStr, ValidationError

from app.core.contracts import EvidenceState, ResultState, SourceRef
from app.modules.transport.contracts import (
    FareOffer,
    FareQuery,
    FareResult,
    FareSegment,
    PlaceRef,
)
from app.modules.transport.providers.base import TransportProviderError

AmadeusEnvironment = Literal["test", "production"]

AMADEUS_ENDPOINTS: dict[AmadeusEnvironment, tuple[str, str]] = {
    "test": (
        "https://test.api.amadeus.com/v1/security/oauth2/token",
        "https://test.api.amadeus.com/v2/shopping/flight-offers",
    ),
    "production": (
        "https://api.amadeus.com/v1/security/oauth2/token",
        "https://api.amadeus.com/v2/shopping/flight-offers",
    ),
}

# This is a deliberately small allow-list, not a city-name guesser. The provider can
# still return a partial offer when an airport is absent, but it will not invent a
# timezone for an untrusted local timestamp.
AIRPORT_TIMEZONES: dict[str, str] = {
    **{
        code: "Asia/Shanghai"
        for code in (
            "PEK",
            "PKX",
            "SHA",
            "PVG",
            "HGH",
            "CAN",
            "SZX",
            "CTU",
            "TFU",
            "CKG",
            "XIY",
            "WUH",
            "NKG",
            "TAO",
            "XMN",
            "KMG",
            "CSX",
            "CGO",
            "TSN",
            "HAK",
            "SYX",
            "URC",
            "HRB",
            "SHE",
            "DLC",
            "FOC",
            "NNG",
            "KWE",
            "TNA",
            "NGB",
            "WNZ",
            "ZUH",
        )
    },
    "HKG": "Asia/Hong_Kong",
    "MFM": "Asia/Macau",
    "TPE": "Asia/Taipei",
    "TSA": "Asia/Taipei",
    "NRT": "Asia/Tokyo",
    "HND": "Asia/Tokyo",
    "KIX": "Asia/Tokyo",
    "ICN": "Asia/Seoul",
    "GMP": "Asia/Seoul",
    "SIN": "Asia/Singapore",
    "BKK": "Asia/Bangkok",
    "KUL": "Asia/Kuala_Lumpur",
    "DXB": "Asia/Dubai",
    "LHR": "Europe/London",
    "CDG": "Europe/Paris",
    "FRA": "Europe/Berlin",
    "JFK": "America/New_York",
    "LAX": "America/Los_Angeles",
    "SFO": "America/Los_Angeles",
}

_IATA_PATTERN = re.compile(r"^[A-Z]{3}$")
_MAX_PASSENGERS = 9
_TOKEN_EXPIRY_SKEW_SECONDS = 5.0
_DEFAULT_TIMEOUT_SECONDS = 8.0
_DEFAULT_MAX_RESPONSE_BYTES = 256 * 1024


class _InvalidOffer(ValueError):
    pass


class AmadeusFareProvider:
    """Read-only Amadeus Flight Offers Search adapter with conservative mapping."""

    provider_id = "amadeus.flight-offers"
    _token_url, _offers_url = AMADEUS_ENDPOINTS["test"]

    def __init__(
        self,
        *,
        environment: AmadeusEnvironment,
        client_id: str | SecretStr,
        client_secret: str | SecretStr,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = _DEFAULT_MAX_RESPONSE_BYTES,
        client: httpx.Client | None = None,
        now: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        if environment not in AMADEUS_ENDPOINTS:
            raise ValueError("Unsupported Amadeus environment.")
        token_url, offers_url = AMADEUS_ENDPOINTS[environment]
        self._token_url = token_url
        self._offers_url = offers_url
        self._client_id = _secret_value(client_id)
        self._client_secret = _secret_value(client_secret)
        if not self._client_id or not self._client_secret:
            raise ValueError("Amadeus credentials must not be blank.")
        if not 0 < timeout_seconds <= 30:
            raise ValueError("Amadeus timeout must be finite and within 30 seconds.")
        if not 0 < max_response_bytes <= 1024 * 1024:
            raise ValueError("Amadeus response limit must be between 1 and 1048576 bytes.")
        self._timeout_seconds = float(timeout_seconds)
        self._max_response_bytes = max_response_bytes
        self._client = client
        self._now = now or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.monotonic
        self._token_lock = threading.Lock()
        self._token: str | None = None
        self._token_expires_at = 0.0

    def search_fares(self, query: FareQuery, *, request_id: UUID) -> FareResult:
        if query.mode != "flight":
            raise TransportProviderError("no_coverage")
        origin_code = _query_iata(query.origin)
        destination_code = _query_iata(query.destination)
        if origin_code is None or destination_code is None:
            raise TransportProviderError("no_coverage")

        child_count = query.child_count or 0
        adult_count = query.passenger_count - child_count
        if adult_count < 1 or query.passenger_count > _MAX_PASSENGERS:
            raise TransportProviderError("policy_unavailable")

        params: dict[str, str | int] = {
            "originLocationCode": origin_code,
            "destinationLocationCode": destination_code,
            "departureDate": query.travel_date.isoformat(),
            "adults": adult_count,
            "currencyCode": "CNY",
            "max": 20,
        }
        if query.child_count is not None:
            params["children"] = child_count

        if self._client is None:
            with httpx.Client(
                timeout=self._timeout_seconds,
                follow_redirects=False,
                verify=True,
                trust_env=False,
            ) as client:
                return self._search_with_client(client, query, params, request_id)
        return self._search_with_client(self._client, query, params, request_id)

    def _search_with_client(
        self,
        client: httpx.Client,
        query: FareQuery,
        params: dict[str, str | int],
        request_id: UUID,
    ) -> FareResult:
        token = self._get_access_token(client)
        payload = self._request_json(
            client,
            "GET",
            self._offers_url,
            request_id=request_id,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            params=params,
        )
        return self._map_response(query, payload, request_id=request_id)

    def _get_access_token(self, client: httpx.Client) -> str:
        with self._token_lock:
            now = self._monotonic()
            if (
                self._token is not None
                and self._token_expires_at > now + _TOKEN_EXPIRY_SKEW_SECONDS
            ):
                return self._token

            payload = self._request_json(
                client,
                "POST",
                self._token_url,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            if not isinstance(payload, dict):
                raise TransportProviderError("unavailable")
            token = payload.get("access_token")
            token_type = payload.get("token_type")
            expires_in = payload.get("expires_in")
            if (
                not isinstance(token, str)
                or not token
                or not isinstance(token_type, str)
                or token_type.casefold() != "bearer"
                or not isinstance(expires_in, int)
                or isinstance(expires_in, bool)
                or expires_in <= 0
            ):
                raise TransportProviderError("unavailable")

            self._token = token
            self._token_expires_at = now + expires_in
            return token

    def _request_json(
        self,
        client: httpx.Client,
        method: str,
        url: str,
        *,
        request_id: UUID | None = None,
        headers: dict[str, str] | None = None,
        params: dict[str, str | int] | None = None,
        data: dict[str, str] | None = None,
    ) -> Any:
        del request_id  # Request IDs are deliberately not sent to the provider.
        try:
            with client.stream(
                method,
                url,
                headers=headers,
                params=params,
                data=data,
                timeout=self._timeout_seconds,
                follow_redirects=False,
            ) as response:
                if not 200 <= response.status_code < 300:
                    raise _status_error(response.status_code)
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > self._max_response_bytes:
                        raise TransportProviderError("unavailable")
                    chunks.append(chunk)
                body = b"".join(chunks)
        except TransportProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise TransportProviderError("unavailable") from exc
        except httpx.RequestError as exc:
            raise TransportProviderError("unavailable") from exc

        try:
            return json.loads(body.decode("utf-8"), parse_float=Decimal)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TransportProviderError("unavailable") from exc

    def _map_response(self, query: FareQuery, payload: Any, *, request_id: UUID) -> FareResult:
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
            raise TransportProviderError("unavailable")
        raw_offers = payload["data"]
        retrieved_at = self._now()
        source = SourceRef(
            source_id=self.provider_id,
            display_name="Amadeus Flight Offers Search",
            url="https://developers.amadeus.com/self-service/category/flights/api-doc/flight-offers-search",
            retrieved_at=retrieved_at,
            evidence_state=EvidenceState.UNKNOWN,
        )
        offers: list[FareOffer] = []
        for index, raw_offer in enumerate(raw_offers):
            try:
                offers.append(
                    self._map_offer(
                        raw_offer,
                        query,
                        source_id=source.source_id,
                        offer_index=index,
                    )
                )
            except (_InvalidOffer, ValidationError, TypeError, ValueError, KeyError, OverflowError):
                continue

        if raw_offers and not offers:
            raise TransportProviderError("unavailable")
        state = ResultState.EMPTY
        if offers:
            state = (
                ResultState.PARTIAL
                if any(offer.missing_fields for offer in offers)
                else ResultState.LIVE
            )
        return FareResult(
            state=state,
            items=offers,
            sources=[source],
            queried_at=retrieved_at,
            request_id=request_id,
        )

    def _map_offer(
        self,
        payload: Any,
        query: FareQuery,
        *,
        source_id: str,
        offer_index: int,
    ) -> FareOffer:
        if not isinstance(payload, dict):
            raise _InvalidOffer("offer is not an object")
        itineraries = payload.get("itineraries")
        if not isinstance(itineraries, list) or len(itineraries) != 1:
            raise _InvalidOffer("one-way offer must have exactly one itinerary")
        itinerary = itineraries[0]
        if not isinstance(itinerary, dict):
            raise _InvalidOffer("invalid itinerary")
        raw_segments = itinerary.get("segments")
        if not isinstance(raw_segments, list) or not raw_segments:
            raise _InvalidOffer("itinerary has no segments")

        origin_code = _query_iata(query.origin)
        destination_code = _query_iata(query.destination)
        if origin_code is None or destination_code is None:
            raise _InvalidOffer("query has no IATA codes")

        segments: list[FareSegment] = []
        segment_departures: list[datetime | None] = []
        segment_arrivals: list[datetime | None] = []
        segment_departure_zones: list[str | None] = []
        segment_arrival_zones: list[str | None] = []
        first_local_departure: datetime | None = None
        previous_arrival_code: str | None = None
        missing_fields: set[str] = set()

        for segment_index, raw_segment in enumerate(raw_segments):
            if not isinstance(raw_segment, dict):
                raise _InvalidOffer("invalid segment")
            departure = raw_segment.get("departure")
            arrival = raw_segment.get("arrival")
            if not isinstance(departure, dict) or not isinstance(arrival, dict):
                raise _InvalidOffer("missing segment endpoint")
            departure_code = _normalize_code(departure.get("iataCode"))
            arrival_code = _normalize_code(arrival.get("iataCode"))
            if departure_code is None or arrival_code is None:
                raise _InvalidOffer("invalid segment IATA code")
            if segment_index == 0 and departure_code != origin_code:
                raise _InvalidOffer("offer origin does not match query")
            if segment_index == len(raw_segments) - 1 and arrival_code != destination_code:
                raise _InvalidOffer("offer destination does not match query")
            if previous_arrival_code is not None and previous_arrival_code != departure_code:
                raise _InvalidOffer("offer segments are not connected")
            previous_arrival_code = arrival_code

            local_departure = _parse_naive_datetime(departure.get("at"))
            local_arrival = _parse_naive_datetime(arrival.get("at"))
            if segment_index == 0:
                first_local_departure = local_departure
            departure_zone = AIRPORT_TIMEZONES.get(departure_code)
            arrival_zone = AIRPORT_TIMEZONES.get(arrival_code)
            departure_at = _localize(local_departure, departure_zone)
            arrival_at = _localize(local_arrival, arrival_zone)
            service_number = _service_number(raw_segment)
            operating_carrier = _operating_carrier(raw_segment)

            if departure_at is None:
                missing_fields.add("departure_at")
            if arrival_at is None:
                missing_fields.add("arrival_at")
            if departure_zone is None:
                missing_fields.add("departure_timezone")
            if arrival_zone is None:
                missing_fields.add("arrival_timezone")
            if service_number is None:
                missing_fields.add("service_number")

            segment_departures.append(departure_at)
            segment_arrivals.append(arrival_at)
            segment_departure_zones.append(departure_zone)
            segment_arrival_zones.append(arrival_zone)
            segments.append(
                FareSegment(
                    segment_id=f"amadeus-segment-{offer_index + 1}-{segment_index + 1}",
                    origin_name=departure_code,
                    destination_name=arrival_code,
                    departure_at=departure_at,
                    arrival_at=arrival_at,
                    departure_timezone=departure_zone,
                    arrival_timezone=arrival_zone,
                    service_number=service_number,
                    operating_carrier=operating_carrier,
                    transfer_place=departure_code if segment_index > 0 else None,
                )
            )

        if first_local_departure is None or first_local_departure.date() != query.travel_date:
            raise _InvalidOffer("offer does not match the requested travel date")

        price_fen, price_basis = _map_party_price(payload, query)
        if price_fen is None:
            missing_fields.add("price_fen")
        if price_basis == "unknown":
            missing_fields.add("price_basis")
        remaining_seats = _optional_nonnegative_int(payload.get("numberOfBookableSeats"))
        if remaining_seats is None:
            missing_fields.add("remaining_seats")
        availability = "unavailable" if remaining_seats == 0 else "unknown"
        if availability == "unknown":
            missing_fields.add("availability")
        missing_fields.add("included_charges")

        direct_service_number = segments[0].service_number if len(segments) == 1 else None
        if len(segments) == 1 and direct_service_number is None:
            missing_fields.add("service_number")

        return FareOffer(
            offer_id=f"amadeus-offer-{offer_index + 1}",
            source_id=source_id,
            mode="flight",
            travel_date=query.travel_date,
            segments=segments,
            service_number=direct_service_number,
            departure_at=segment_departures[0],
            arrival_at=segment_arrivals[-1],
            departure_timezone=segment_departure_zones[0],
            arrival_timezone=segment_arrival_zones[-1],
            origin_name=query.origin.display_name,
            destination_name=query.destination.display_name,
            price_fen=price_fen,
            currency_code="CNY",
            price_basis=price_basis,
            price_scope="entire_journey",
            passenger_count=query.passenger_count,
            included_charges=[],
            availability=availability,
            remaining_seats=remaining_seats,
            evidence_state=EvidenceState.UNKNOWN,
            missing_fields=sorted(missing_fields),
        )


def _secret_value(value: str | SecretStr) -> str:
    if isinstance(value, SecretStr):
        return value.get_secret_value().strip()
    if isinstance(value, str):
        return value.strip()
    raise TypeError("Amadeus credential must be a string or SecretStr.")


def _status_error(status_code: int) -> TransportProviderError:
    if status_code in (401, 403):
        return TransportProviderError("policy_unavailable")
    if status_code == 429:
        return TransportProviderError("rate_limited")
    return TransportProviderError("unavailable")


def _query_iata(place: PlaceRef) -> str | None:
    code = place.place_id
    if code is None or _IATA_PATTERN.fullmatch(code) is None:
        return None
    return code


def _normalize_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    code = value.strip().upper()
    return code if _IATA_PATTERN.fullmatch(code) is not None else None


def _parse_naive_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00" if value.endswith("Z") else value)
    except ValueError:
        return None
    if parsed.tzinfo is not None and parsed.utcoffset() is not None:
        return None
    return parsed


def _localize(value: datetime | None, timezone: str | None) -> datetime | None:
    if value is None or timezone is None:
        return None
    try:
        return value.replace(tzinfo=ZoneInfo(timezone)).astimezone(UTC)
    except (ValueError, KeyError):
        return None


def _service_number(segment: dict[str, Any]) -> str | None:
    carrier = _normalize_carrier(segment.get("carrierCode"))
    number = segment.get("number")
    if carrier is None or not isinstance(number, str) or not number.strip():
        return None
    value = f"{carrier}{number.strip()}"
    return value if len(value) <= 80 else None


def _operating_carrier(segment: dict[str, Any]) -> str | None:
    operating = segment.get("operating")
    if not isinstance(operating, dict):
        return None
    return _normalize_carrier(operating.get("carrierCode"))


def _normalize_carrier(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    carrier = value.strip().upper()
    if not carrier or len(carrier) > 160 or not carrier.isalnum():
        return None
    return carrier


def _map_party_price(
    offer: dict[str, Any], query: FareQuery
) -> tuple[int | None, Literal["party_total", "unknown"]]:
    price = offer.get("price")
    traveler_pricings = offer.get("travelerPricings")
    if not isinstance(price, dict) or not isinstance(traveler_pricings, list):
        return None, "unknown"
    if len(traveler_pricings) != query.passenger_count or price.get("currency") != "CNY":
        return None, "unknown"

    total = price.get("total")
    total_fen = _money_to_fen(total)
    if total_fen is None:
        return None, "unknown"

    expected_children = query.child_count or 0
    expected_adults = query.passenger_count - expected_children
    adult_count = 0
    child_count = 0
    traveler_total = Decimal("0")
    for traveler in traveler_pricings:
        if not isinstance(traveler, dict):
            return None, "unknown"
        traveler_type = traveler.get("travelerType")
        traveler_price = traveler.get("price")
        if not isinstance(traveler_price, dict):
            return None, "unknown"
        if traveler_price.get("currency") != "CNY":
            return None, "unknown"
        amount = _decimal_money(traveler_price.get("total"))
        if amount is None:
            return None, "unknown"
        traveler_total += amount
        if traveler_type == "ADULT":
            adult_count += 1
        elif traveler_type == "CHILD":
            child_count += 1
        else:
            return None, "unknown"

    if adult_count != expected_adults or child_count != expected_children:
        return None, "unknown"
    if traveler_total != _decimal_money(total):
        return None, "unknown"
    return total_fen, "party_total"


def _money_to_fen(value: Any) -> int | None:
    amount = _decimal_money(value)
    if amount is None:
        return None
    scaled = amount * 100
    if scaled != scaled.to_integral_value():
        return None
    try:
        return int(scaled)
    except (ValueError, OverflowError):
        return None


def _decimal_money(value: Any) -> Decimal | None:
    if isinstance(value, bool) or isinstance(value, float):
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    if not amount.is_finite() or amount < 0:
        return None
    if amount.as_tuple().exponent < -2:
        return None
    return amount


def _optional_nonnegative_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value
