from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest

from app.core.contracts import EvidenceState, ResultState, SourceRef
from app.modules.transport.contracts import (
    FareOffer,
    FareQuery,
    FareResult,
    PlaceRef,
    RouteOption,
    RouteQuery,
    RouteResult,
)
from app.modules.transport.providers.base import TransportProviderError
from app.modules.transport.providers.fake import (
    FakeFareProvider,
    FakeRouteProvider,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "transport"
REQUEST_ID = UUID("b5c82294-cf76-4b61-91bb-f76868a56351")
NOW = datetime(2026, 10, 28, 2, 0, tzinfo=UTC)


def fare_result() -> FareResult:
    data = json.loads((FIXTURE_DIR / "fares.json").read_text(encoding="utf-8"))
    offer = FareOffer.model_validate_json(json.dumps(data["direct_flight"]))
    return FareResult(
        state=ResultState.DEMO,
        items=[offer],
        sources=[
            SourceRef(
                source_id="fixture.transport.fares",
                display_name="合成票价 fixture",
                retrieved_at=NOW,
                evidence_state=EvidenceState.DEMO,
            )
        ],
        queried_at=NOW,
        request_id=REQUEST_ID,
    )


def route_result() -> RouteResult:
    data = json.loads((FIXTURE_DIR / "routes.json").read_text(encoding="utf-8"))
    route = RouteOption.model_validate_json(json.dumps(data["walking_route"]))
    source = SourceRef(
        source_id="fixture.transport.routes",
        display_name="合成路线 fixture",
        retrieved_at=NOW,
        evidence_state=EvidenceState.DEMO,
    )
    return RouteResult(
        state=ResultState.DEMO,
        items=[route],
        sources=[source],
        queried_at=NOW,
        request_id=REQUEST_ID,
    )


def test_fake_fare_provider_returns_explicit_result_and_records_query() -> None:
    query = FareQuery(
        origin=PlaceRef(display_name="上海虹桥"),
        destination=PlaceRef(display_name="杭州萧山"),
        mode="flight",
        travel_date=date(2026, 11, 10),
        passenger_count=2,
    )
    result = fare_result()
    provider = FakeFareProvider(result=result)

    actual = provider.search_fares(query, request_id=REQUEST_ID)

    assert actual is result
    assert len(provider.calls) == 1
    assert provider.calls[0].query == query
    assert provider.calls[0].request_id == REQUEST_ID
    assert actual.items[0].mode == "flight"
    assert actual.items[0].source_id == actual.sources[0].source_id


def test_fake_route_provider_keeps_route_query_mode_and_result_separate() -> None:
    query = RouteQuery(
        origin=PlaceRef(display_name="起点 A"),
        destination=PlaceRef(display_name="目的地 B"),
        mode="walking",
    )
    result = route_result()
    provider = FakeRouteProvider(result=result)

    actual = provider.search_route(query, request_id=REQUEST_ID)

    assert actual is result
    assert provider.calls[0].query == query
    assert provider.calls[0].query.mode == "walking"
    assert actual.items[0].mode == "walking"
    assert actual.items[0].source_id == "fixture.transport.routes"


@pytest.mark.parametrize(
    "status",
    ["unconfigured", "no_coverage", "rate_limited", "policy_unavailable", "unavailable"],
)
def test_fake_provider_error_is_safe_and_does_not_expose_raw_provider_payload(status: str) -> None:
    private_message = "secret-token private-coordinate vendor-response"
    error = TransportProviderError(status, private_message)
    provider = FakeFareProvider(error=error)
    query = FareQuery(
        origin=PlaceRef(display_name="起点 sentinel"),
        destination=PlaceRef(display_name="终点 sentinel"),
        mode="rail",
        travel_date=date(2026, 11, 10),
        passenger_count=1,
    )

    with pytest.raises(TransportProviderError) as captured:
        provider.search_fares(query, request_id=REQUEST_ID)

    assert captured.value.status == status
    assert private_message not in str(captured.value)
    assert provider.calls[0].request_id == REQUEST_ID


def test_fake_provider_without_result_raises_unconfigured_instead_of_returning_demo() -> None:
    provider = FakeRouteProvider()
    query = RouteQuery(
        origin=PlaceRef(display_name="起点 A"),
        destination=PlaceRef(display_name="目的地 B"),
        mode="transit",
    )

    with pytest.raises(TransportProviderError) as captured:
        provider.search_route(query, request_id=REQUEST_ID)

    assert captured.value.status == "unconfigured"
    assert provider.calls[0].query.mode == "transit"


def test_fake_provider_rejects_ambiguous_result_and_error_configuration() -> None:
    with pytest.raises(ValueError):
        FakeFareProvider(result=fare_result(), error=TransportProviderError("unavailable"))

    with pytest.raises(ValueError):
        FakeRouteProvider(result=route_result(), error=TransportProviderError("unavailable"))


def test_provider_error_rejects_unknown_status_without_retaining_raw_text() -> None:
    with pytest.raises(ValueError):
        TransportProviderError("vendor-secret-status", "secret response")
