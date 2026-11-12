from __future__ import annotations

import re
from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from app.core.contracts import EvidenceState, ResultState, SourceRef
from app.modules.transport.contracts import (
    FareOffer,
    FareQuery,
    FareResult,
    FareSegment,
    validate_fare_booking_url,
)
from app.modules.transport.providers.amadeus import AIRPORT_TIMEZONES
from app.modules.transport.providers.base import TransportProviderError
from app.modules.transport.providers.flyai import FlyAITrainFareProvider, _text


class FlyAIFlightFareProvider(FlyAITrainFareProvider):
    """Official CLI flight search with independent, conservative fare semantics."""

    provider_id = "flyai.search-flight"
    mode = "flight"

    def validate_query(self, query: FareQuery) -> None:
        codes = [
            (place.place_id or "").strip().upper() for place in (query.origin, query.destination)
        ]
        if (
            not all(re.fullmatch(r"[A-Z]{3}", code) for code in codes)
            or codes[0] == codes[1]
            or query.passenger_count > 9
            or (query.child_count or 0) >= query.passenger_count
        ):
            raise TransportProviderError("no_coverage")

    @staticmethod
    def map_result(payload, query, *, request_id, now):
        return map_flight_result(payload, query, request_id=request_id, now=now)


def _flight_time(value: object, airport: object) -> tuple[datetime | None, str | None]:
    zone = AIRPORT_TIMEZONES.get(airport) if isinstance(airport, str) else None
    text = _text(value, 40)
    if text is None:
        return None, zone
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            if zone is None:
                return None, None
            parsed = parsed.replace(tzinfo=ZoneInfo(zone))
        return parsed.astimezone(UTC), zone
    except ValueError:
        return None, zone


def _flight_offer(item: dict, index: int, query: FareQuery) -> FareOffer:
    journeys = item.get("journeys")
    if not isinstance(journeys, list) or len(journeys) != 1:
        raise ValueError("Expected one-way journey.")
    journey = journeys[0]
    rows = journey.get("segments") if isinstance(journey, dict) else None
    if (
        not isinstance(rows, list)
        or not 1 <= len(rows) <= 10
        or not all(isinstance(row, dict) for row in rows)
    ):
        raise ValueError("Invalid flight segments.")
    if (
        rows[0].get("depStationCode") != (query.origin.place_id or "").upper()
        or rows[-1].get("arrStationCode") != (query.destination.place_id or "").upper()
    ):
        raise ValueError("Flight endpoints do not match selected airports.")
    departure = _text(rows[0].get("depDateTime"), 40)
    if departure is None or date.fromisoformat(departure[:10]) != query.travel_date:
        raise ValueError("Flight date mismatch.")
    legs = []
    for n, row in enumerate(rows):
        if row.get("transportType") not in {"飞机", "flight", "Flight", "FLIGHT", "air"}:
            raise ValueError("Wrong transport type.")
        dep, dep_zone = _flight_time(row.get("depDateTime"), row.get("depStationCode"))
        arr, arr_zone = _flight_time(row.get("arrDateTime"), row.get("arrStationCode"))
        if n and rows[n - 1].get("arrStationCode") != row.get("depStationCode"):
            raise ValueError("Disconnected flight itinerary.")
        if legs and legs[-1].arrival_at and dep and dep < legs[-1].arrival_at:
            raise ValueError("Unordered flight itinerary.")
        legs.append(
            FareSegment(
                segment_id=f"flight-leg-{n}",
                origin_name=_text(row.get("depStationName"), 240),
                destination_name=_text(row.get("arrStationName"), 240),
                departure_at=dep,
                arrival_at=arr,
                departure_timezone=dep_zone,
                arrival_timezone=arr_zone,
                service_number=_text(row.get("marketingTransportNo"), 80),
                seat_class=_text(row.get("seatClassName"), 120),
                operating_carrier=_text(row.get("marketingTransportName"), 160),
            )
        )
    first, last = legs[0], legs[-1]
    if not first.origin_name or not last.destination_name:
        raise ValueError("Missing airport names.")
    missing = [
        "price_fen",
        "price_basis",
        "price_scope",
        "passenger_count",
        "remaining_seats",
        "availability",
        "included_charges",
    ]
    for field in ("departure_at", "departure_timezone"):
        if getattr(first, field) is None:
            missing.append(field)
    for field in ("arrival_at", "arrival_timezone"):
        if getattr(last, field) is None:
            missing.append(field)
    if len(legs) == 1 and first.service_number is None:
        missing.append("service_number")
    try:
        booking_url = validate_fare_booking_url(_text(item.get("jumpUrl"), 4096))
    except ValueError:
        booking_url = None
    # adultPrice alone does not prove tax, scope or the requested party/child pricing.
    return FareOffer(
        offer_id=f"flyai-flight-{index}",
        source_id=FlyAIFlightFareProvider.provider_id,
        mode="flight",
        travel_date=query.travel_date,
        segments=legs,
        service_number=first.service_number if len(legs) == 1 else None,
        origin_name=first.origin_name,
        destination_name=last.destination_name,
        departure_at=first.departure_at,
        arrival_at=last.arrival_at,
        departure_timezone=first.departure_timezone,
        arrival_timezone=last.arrival_timezone,
        price_basis="unknown",
        price_scope="unknown",
        evidence_state=EvidenceState.VERIFIED,
        missing_fields=missing,
        booking_url=booking_url,
    )


def map_flight_result(
    payload: object, query: FareQuery, *, request_id: UUID, now: datetime
) -> FareResult:
    if (
        not isinstance(payload, dict)
        or type(payload.get("status")) is not int
        or payload["status"] != 0
    ):
        raise ValueError("Invalid flight business response.")
    data = payload.get("data")
    rows = data.get("itemList") if isinstance(data, dict) else None
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Invalid flight result list.")
    items = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        try:
            items.append(_flight_offer(row, index, query))
        except ValueError, TypeError, ValidationError:
            continue
    if rows and not items:
        raise ValueError("No matching flight result.")
    return FareResult(
        state=ResultState.PARTIAL if items else ResultState.EMPTY,
        items=items,
        sources=[
            SourceRef(
                source_id=FlyAIFlightFareProvider.provider_id,
                display_name="飞猪 FlyAI 航班查询",
                url="https://flyai.open.fliggy.com/",
                retrieved_at=now,
                attribution=("基于飞猪 FlyAI 实时搜索；未核实所选人数、儿童报价、"
                             "税费与余量，以供应商详情为准。"),
                evidence_state=EvidenceState.VERIFIED,
            )
        ],
        queried_at=now,
        request_id=request_id,
        platform_hint=_text(payload.get("systemMessage"), 2000)
        or _text(data.get("systemMessage"), 2000),
    )
