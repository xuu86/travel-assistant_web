from __future__ import annotations

import copy
import logging
from datetime import UTC, date, datetime
from urllib.parse import parse_qs
from uuid import uuid4

import httpx
import pytest

from app.core.contracts import ResultState
from app.modules.transport.contracts import FareQuery, PlaceRef
from app.modules.transport.providers.amadeus import (
    AIRPORT_TIMEZONES,
    AMADEUS_ENDPOINTS,
    AmadeusFareProvider,
)
from app.modules.transport.providers.base import TransportProviderError

TOKEN = "fixture-access-token-never-log"
CLIENT_ID = "fixture-client-id-never-log"
CLIENT_SECRET = "fixture-client-secret-never-log"
NOW = datetime(2026, 10, 30, 3, 0, tzinfo=UTC)
REQUEST_ID = uuid4()


def _query(
    *,
    passenger_count: int = 2,
    child_count: int | None = None,
    origin: str = "SHA",
    destination: str = "HGH",
) -> FareQuery:
    return FareQuery(
        origin=PlaceRef(display_name="上海虹桥", place_id=origin),
        destination=PlaceRef(display_name="杭州萧山", place_id=destination),
        mode="flight",
        travel_date=date(2026, 11, 10),
        passenger_count=passenger_count,
        child_count=child_count,
    )


def _offer(*, origin: str = "SHA", destination: str = "HGH") -> dict[str, object]:
    return {
        "itineraries": [
            {
                "segments": [
                    {
                        "departure": {"iataCode": origin, "at": "2026-11-10T08:00:00"},
                        "arrival": {"iataCode": destination, "at": "2026-11-10T09:10:00"},
                        "carrierCode": "MU",
                        "number": "1234",
                    }
                ]
            }
        ],
        "price": {"currency": "CNY", "total": "355.34"},
        "travelerPricings": [
            {"travelerType": "ADULT", "price": {"currency": "CNY", "total": "177.67"}},
            {"travelerType": "ADULT", "price": {"currency": "CNY", "total": "177.67"}},
        ],
        "numberOfBookableSeats": 3,
    }


def _token_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={"access_token": TOKEN, "token_type": "Bearer", "expires_in": 60},
    )


def _provider(
    handler,
    *,
    environment: str = "test",
    client: httpx.Client | None = None,
    monotonic=None,
    max_response_bytes: int = 256 * 1024,
) -> AmadeusFareProvider:
    return AmadeusFareProvider(
        environment=environment,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        client=client or httpx.Client(transport=httpx.MockTransport(handler)),
        now=lambda: NOW,
        monotonic=monotonic,
        max_response_bytes=max_response_bytes,
    )


def _successful_handler() -> tuple[object, list[httpx.Request]]:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            assert str(request.url) == AMADEUS_ENDPOINTS["test"][0]
            form = parse_qs(request.content.decode())
            assert form == {
                "grant_type": ["client_credentials"],
                "client_id": [CLIENT_ID],
                "client_secret": [CLIENT_SECRET],
            }
            assert "x-request-id" not in request.headers
            return _token_response()

        assert str(request.url).split("?")[0] == AMADEUS_ENDPOINTS["test"][1]
        assert request.headers["authorization"] == f"Bearer {TOKEN}"
        assert "x-request-id" not in request.headers
        params = dict(request.url.params)
        assert params == {
            "originLocationCode": "SHA",
            "destinationLocationCode": "HGH",
            "departureDate": "2026-11-10",
            "adults": "2",
            "currencyCode": "CNY",
            "max": "20",
        }
        return httpx.Response(200, json={"data": [_offer()]})

    return handler, requests


def test_request_uses_fixed_endpoint_oauth_query_and_maps_party_total_and_seats() -> None:
    handler, requests = _successful_handler()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _provider(handler, client=client).search_fares(_query(), request_id=REQUEST_ID)

    assert len(requests) == 2
    assert result.request_id == REQUEST_ID
    assert result.state is ResultState.PARTIAL
    assert result.items[0].price_fen == 35534
    assert result.items[0].price_basis == "party_total"
    assert result.items[0].price_scope == "entire_journey"
    assert result.items[0].passenger_count == 2
    assert result.items[0].remaining_seats == 3
    assert "price_scope" not in result.items[0].missing_fields
    assert result.items[0].departure_at == datetime(2026, 11, 10, 0, 0, tzinfo=UTC)
    assert result.items[0].arrival_at == datetime(2026, 11, 10, 1, 10, tzinfo=UTC)


def test_oauth_token_is_cached_and_refreshed_before_expiry() -> None:
    clock = [0.0]
    token_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls
        if request.method == "POST":
            token_calls += 1
            return _token_response()
        return httpx.Response(200, json={"data": [_offer()]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = _provider(handler, client=client, monotonic=lambda: clock[0])
        provider.search_fares(_query(), request_id=REQUEST_ID)
        provider.search_fares(_query(), request_id=REQUEST_ID)
        assert token_calls == 1

        clock[0] = 54.0
        provider.search_fares(_query(), request_id=REQUEST_ID)
        assert token_calls == 1

        clock[0] = 56.0
        provider.search_fares(_query(), request_id=REQUEST_ID)
        assert token_calls == 2


def test_children_are_sent_separately_and_expected_traveler_types_are_enforced() -> None:
    query = _query(passenger_count=3, child_count=1)
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "POST":
            return _token_response()
        params = dict(request.url.params)
        assert params["adults"] == "2"
        assert params["children"] == "1"
        offer = _offer()
        offer["price"] = {"currency": "CNY", "total": "600.00"}
        offer["travelerPricings"] = [
            {"travelerType": "ADULT", "price": {"currency": "CNY", "total": "200.00"}},
            {"travelerType": "ADULT", "price": {"currency": "CNY", "total": "200.00"}},
            {"travelerType": "INFANT", "price": {"currency": "CNY", "total": "200.00"}},
        ]
        return httpx.Response(200, json={"data": [offer]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _provider(handler, client=client).search_fares(query, request_id=REQUEST_ID)

    assert len(requests) == 2
    assert result.items[0].price_fen is None
    assert result.items[0].price_basis == "unknown"
    assert "price_fen" in result.items[0].missing_fields
    assert "price_basis" in result.items[0].missing_fields


@pytest.mark.parametrize("environment", ["test", "production"])
def test_only_official_environment_hosts_are_used(environment: str) -> None:
    token_url, offers_url = AMADEUS_ENDPOINTS[environment]

    def handler(request: httpx.Request) -> httpx.Response:
        expected = token_url if request.method == "POST" else offers_url
        assert str(request.url).split("?")[0] == expected
        if request.method == "POST":
            return _token_response()
        return httpx.Response(200, json={"data": [_offer()]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _provider(handler, environment=environment, client=client).search_fares(
            _query(), request_id=REQUEST_ID
        )

    assert result.items[0].offer_id == "amadeus-offer-1"


def test_empty_data_is_an_explicit_empty_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _token_response()
        return httpx.Response(200, json={"data": []})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _provider(handler, client=client).search_fares(_query(), request_id=REQUEST_ID)

    assert result.state is ResultState.EMPTY
    assert result.items == []
    assert len(result.sources) == 1


def test_unknown_airport_timezone_keeps_times_unknown_instead_of_inventing_them() -> None:
    query = _query(origin="ZZZ", destination="YYY")
    assert "ZZZ" not in AIRPORT_TIMEZONES
    assert "YYY" not in AIRPORT_TIMEZONES

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _token_response()
        return httpx.Response(
            200,
            json={"data": [_offer(origin="ZZZ", destination="YYY")]},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        result = _provider(handler, client=client).search_fares(query, request_id=REQUEST_ID)

    offer = result.items[0]
    assert result.state is ResultState.PARTIAL
    assert offer.departure_at is None
    assert offer.arrival_at is None
    assert offer.departure_timezone is None
    assert offer.arrival_timezone is None
    assert {"departure_at", "arrival_at", "departure_timezone", "arrival_timezone"}.issubset(
        offer.missing_fields
    )


def _map_offer_with(overrides: dict[str, object], *, query: FareQuery | None = None):
    payload = copy.deepcopy(_offer())
    payload.update(overrides)
    provider = _provider(lambda _: httpx.Response(500))
    return provider._map_offer(
        payload,
        query or _query(),
        source_id=provider.provider_id,
        offer_index=0,
    )


@pytest.mark.parametrize(
    "mutator",
    [
        lambda offer: offer["price"].update({"currency": "USD"}),
        lambda offer: offer["price"].update({"total": "355.345"}),
        lambda offer: offer.__setitem__("travelerPricings", offer["travelerPricings"][:1]),
        lambda offer: offer["travelerPricings"][0].update({"travelerType": "CHILD"}),
    ],
)
def test_ambiguous_currency_precision_or_passenger_pricing_fails_closed(mutator) -> None:
    payload = copy.deepcopy(_offer())
    mutator(payload)
    provider = _provider(lambda _: httpx.Response(500))
    offer = provider._map_offer(
        payload,
        _query(),
        source_id=provider.provider_id,
        offer_index=0,
    )

    assert offer.price_fen is None
    assert offer.price_basis == "unknown"
    assert "price_fen" in offer.missing_fields
    assert "price_basis" in offer.missing_fields


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (401, "policy_unavailable"),
        (403, "policy_unavailable"),
        (429, "rate_limited"),
        (400, "unavailable"),
        (500, "unavailable"),
    ],
)
def test_upstream_offer_statuses_are_mapped_without_upstream_body(
    status: int, expected: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _token_response()
        return httpx.Response(status, text=f"private upstream body {TOKEN}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = _provider(handler, client=client)
        with pytest.raises(TransportProviderError) as error:
            provider.search_fares(_query(), request_id=REQUEST_ID)

    assert error.value.status == expected
    assert "private upstream" not in str(error.value)
    assert TOKEN not in str(error.value)


@pytest.mark.parametrize("body", [b"not-json", b"\xff\xfe"])
def test_malformed_or_non_utf8_responses_fail_closed(body: bytes) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _token_response()
        return httpx.Response(200, content=body)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TransportProviderError) as error:
            _provider(handler, client=client).search_fares(_query(), request_id=REQUEST_ID)

    assert error.value.status == "unavailable"


def test_oversized_response_is_rejected_and_details_are_not_retained() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _token_response()
        return httpx.Response(200, content=b"x" * 513)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        provider = _provider(handler, client=client, max_response_bytes=512)
        with pytest.raises(TransportProviderError) as error:
            provider.search_fares(_query(), request_id=REQUEST_ID)

    assert error.value.status == "unavailable"
    assert "x" * 20 not in str(error.value)


@pytest.mark.parametrize(
    "exception",
    [
        httpx.ReadTimeout("private timeout details"),
        httpx.ConnectError("private connection details"),
    ],
)
def test_network_failures_are_sanitized(exception: Exception) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _token_response()
        raise exception

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TransportProviderError) as error:
            _provider(handler, client=client).search_fares(_query(), request_id=REQUEST_ID)

    assert error.value.status == "unavailable"
    assert "private" not in str(error.value)
    assert TOKEN not in str(error.value)


def test_redirects_are_not_followed_even_when_the_injected_client_allows_them() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.method == "POST":
            return _token_response()
        return httpx.Response(302, headers={"location": "https://evil.example/collect"})

    with httpx.Client(
        transport=httpx.MockTransport(handler), follow_redirects=True
    ) as client:
        with pytest.raises(TransportProviderError) as error:
            _provider(handler, client=client).search_fares(_query(), request_id=REQUEST_ID)

    assert error.value.status == "unavailable"
    assert len(calls) == 2
    assert all("evil.example" not in url for url in calls)


def test_default_client_requires_tls_and_disables_environment_proxy_discovery(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FailingClient:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)
            raise RuntimeError("client construction reached")

    monkeypatch.setattr("app.modules.transport.providers.amadeus.httpx.Client", FailingClient)

    provider = AmadeusFareProvider(
        environment="test",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
    )
    with pytest.raises(RuntimeError, match="client construction reached"):
        provider.search_fares(_query(), request_id=REQUEST_ID)

    assert captured["verify"] is True
    assert captured["follow_redirects"] is False
    assert captured["trust_env"] is False


def test_invalid_token_payload_is_not_logged_or_reflected() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"access_token": TOKEN, "token_type": "not-bearer", "expires_in": 60},
        )

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(TransportProviderError) as error:
            _provider(handler, client=client).search_fares(_query(), request_id=REQUEST_ID)

    assert error.value.status == "unavailable"
    assert TOKEN not in str(error.value)
    assert "not-bearer" not in str(error.value)


def test_provider_does_not_log_query_prices_tokens_or_upstream_text(caplog) -> None:
    caplog.set_level(logging.DEBUG, logger="app.transport")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return _token_response()
        return httpx.Response(200, json={"data": [_offer()]})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        _provider(handler, client=client).search_fares(_query(), request_id=REQUEST_ID)

    assert caplog.text == ""
    assert TOKEN not in caplog.text
    assert CLIENT_SECRET not in caplog.text
    assert "355.34" not in caplog.text
    assert "上海虹桥" not in caplog.text