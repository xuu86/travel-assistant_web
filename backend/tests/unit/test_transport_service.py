from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from app.core.contracts import ErrorCode, EvidenceState, ResultState, SourceRef
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
from app.modules.transport.service import TransportService

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "transport"
REQUEST_ID = UUID("5ee0df47-6575-4fb3-91a8-c69ec89e93bf")
OTHER_REQUEST_ID = UUID("10ebcb51-67cd-40bc-bd8a-f307f553abf2")
NOW = datetime(2026, 10, 28, 2, 0, tzinfo=UTC)
TRAVEL_DATE = datetime(2026, 11, 10, tzinfo=UTC).date()


def fare_payload(name: str = "direct_flight") -> dict[str, object]:
    return json.loads((FIXTURE_DIR / "fares.json").read_text(encoding="utf-8"))[name]


def route_payload(name: str = "walking_route") -> dict[str, object]:
    return json.loads((FIXTURE_DIR / "routes.json").read_text(encoding="utf-8"))[name]


def fare_result(name: str = "direct_flight") -> FareResult:
    offer = FareOffer.model_validate_json(json.dumps(fare_payload(name)))
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
        request_id=OTHER_REQUEST_ID,
    )


def route_result(name: str = "walking_route") -> RouteResult:
    route = RouteOption.model_validate_json(json.dumps(route_payload(name)))
    return RouteResult(
        state=ResultState.DEMO,
        items=[route],
        sources=[
            SourceRef(
                source_id="fixture.transport.routes",
                display_name="合成路线 fixture",
                retrieved_at=NOW,
                evidence_state=EvidenceState.DEMO,
            )
        ],
        queried_at=NOW,
        request_id=OTHER_REQUEST_ID,
    )


def fare_query(
    *, mode: str = "flight", travel_date=None, passenger_count: int = 2
) -> FareQuery:
    return FareQuery(
        origin=PlaceRef(display_name="上海虹桥"),
        destination=PlaceRef(display_name="杭州萧山"),
        mode=mode,
        travel_date=travel_date or TRAVEL_DATE,
        passenger_count=passenger_count,
    )


def route_query(*, mode: str = "walking") -> RouteQuery:
    return RouteQuery(
        origin=PlaceRef(display_name="起点 A"),
        destination=PlaceRef(display_name="目的地 B"),
        mode=mode,
    )


def test_unconfigured_services_return_empty_safe_results_without_provider_calls() -> None:
    service = TransportService(now=lambda: NOW)

    fare = service.search_fares(fare_query(), request_id=REQUEST_ID)
    route = service.search_route(route_query(), request_id=REQUEST_ID)

    assert fare.state is ResultState.UNCONFIGURED
    assert route.state is ResultState.UNCONFIGURED
    assert fare.items == route.items == []
    assert fare.sources == route.sources == []
    assert fare.error is not None and fare.error.code is ErrorCode.UNCONFIGURED
    assert route.error is not None and route.error.request_id == REQUEST_ID
    assert fare.request_id == route.request_id == REQUEST_ID
    assert fare.queried_at == route.queried_at == NOW


@pytest.mark.parametrize(
    ("status", "expected_state", "expected_code"),
    [
        ("unconfigured", ResultState.UNCONFIGURED, ErrorCode.UNCONFIGURED),
        ("no_coverage", ResultState.NO_COVERAGE, ErrorCode.NO_COVERAGE),
        ("rate_limited", ResultState.RATE_LIMITED, ErrorCode.RATE_LIMITED),
        ("policy_unavailable", ResultState.POLICY_UNAVAILABLE, ErrorCode.POLICY_UNAVAILABLE),
        ("unavailable", ResultState.UNAVAILABLE, ErrorCode.PROVIDER_UNAVAILABLE),
    ],
)
def test_provider_status_maps_to_public_empty_result_without_leaking_error_text(
    status: str, expected_state: ResultState, expected_code: ErrorCode
) -> None:
    secret = "private-location vendor-secret-response"
    service = TransportService(
        fare_provider=FakeFareProvider(error=TransportProviderError(status, secret)),
        now=lambda: NOW,
    )

    result = service.search_fares(fare_query(), request_id=REQUEST_ID)

    assert result.state is expected_state
    assert result.items == []
    assert result.error is not None and result.error.code is expected_code
    assert result.error.request_id == REQUEST_ID
    assert result.request_id == REQUEST_ID
    assert secret not in result.message
    assert secret not in result.error.message


def test_successful_fare_result_matches_query_and_keeps_time_source_and_evidence() -> None:
    result = fare_result()
    fake = FakeFareProvider(result=result)
    service = TransportService(fare_provider=fake, now=lambda: NOW + timedelta(days=2))

    actual = service.search_fares(fare_query(), request_id=REQUEST_ID)

    assert actual.state is ResultState.DEMO
    assert actual.request_id == REQUEST_ID
    assert actual.queried_at == NOW
    assert actual.sources[0].retrieved_at == NOW
    assert actual.items[0].evidence_state is EvidenceState.DEMO
    assert "fixture" in actual.message
    assert fake.calls[0].query.travel_date == TRAVEL_DATE
    assert fake.calls[0].request_id == REQUEST_ID


def test_live_verified_fare_preserves_provider_evidence_and_source() -> None:
    payload = {
        **fare_payload(),
        "remaining_seats": 4,
        "availability": "available",
        "evidence_state": "verified",
        "missing_fields": [],
    }
    offer = FareOffer.model_validate_json(json.dumps(payload))
    source = SourceRef(
        source_id="fixture.transport.fares",
        display_name="Synthetic verified-source contract test",
        retrieved_at=NOW,
        evidence_state=EvidenceState.VERIFIED,
    )
    provider_result = FareResult(
        state=ResultState.LIVE,
        items=[offer],
        sources=[source],
        queried_at=NOW,
        request_id=OTHER_REQUEST_ID,
    )
    service = TransportService(
        fare_provider=FakeFareProvider(result=provider_result), now=lambda: NOW
    )

    result = service.search_fares(fare_query(), request_id=REQUEST_ID)

    assert result.state is ResultState.LIVE
    assert result.items[0].evidence_state is EvidenceState.VERIFIED
    assert result.sources[0].evidence_state is EvidenceState.VERIFIED
    assert result.request_id == REQUEST_ID


@pytest.mark.parametrize(
    "mutated_offer",
    [
        {"mode": "rail"},
        {"travel_date": "2026-11-11"},
        {"passenger_count": 1},
    ],
)
def test_fare_result_mismatching_mode_date_or_passenger_count_is_unavailable(
    mutated_offer: dict[str, object],
) -> None:
    payload = {**fare_payload(), **mutated_offer}
    offer = FareOffer.model_validate_json(json.dumps(payload))
    result = fare_result().model_copy(update={"items": [offer]})
    service = TransportService(fare_provider=FakeFareProvider(result=result), now=lambda: NOW)

    actual = service.search_fares(fare_query(), request_id=REQUEST_ID)

    assert actual.state is ResultState.UNAVAILABLE
    assert actual.items == []
    assert actual.error is not None
    assert actual.error.code is ErrorCode.PROVIDER_UNAVAILABLE


def test_party_total_fare_must_refer_to_the_requested_passenger_count() -> None:
    offer = FareOffer.model_validate_json(json.dumps(fare_payload("rail_transfer")))
    result = fare_result().model_copy(update={"items": [offer]})
    service = TransportService(fare_provider=FakeFareProvider(result=result), now=lambda: NOW)

    actual = service.search_fares(
        fare_query(mode="rail", passenger_count=3), request_id=REQUEST_ID
    )

    assert actual.state is ResultState.UNAVAILABLE
    assert actual.items == []


def test_provider_result_request_id_is_rebound_but_query_time_is_not_fabricated() -> None:
    result = fare_result()
    service = TransportService(fare_provider=FakeFareProvider(result=result), now=lambda: NOW)

    actual = service.search_fares(fare_query(), request_id=REQUEST_ID)

    assert actual.request_id == REQUEST_ID
    assert actual.queried_at == result.queried_at
    assert actual.sources == result.sources


def test_empty_and_no_coverage_results_remain_distinct() -> None:
    empty = FareResult(
        state=ResultState.EMPTY,
        items=[],
        sources=[],
        queried_at=NOW,
        request_id=OTHER_REQUEST_ID,
        message="provider raw message must not be shown",
    )
    no_coverage = FareResult(
        state=ResultState.NO_COVERAGE,
        items=[],
        sources=[],
        queried_at=NOW,
        request_id=OTHER_REQUEST_ID,
    )
    empty_service = TransportService(
        fare_provider=FakeFareProvider(result=empty), now=lambda: NOW
    )
    no_coverage_service = TransportService(
        fare_provider=FakeFareProvider(result=no_coverage), now=lambda: NOW
    )

    empty_result = empty_service.search_fares(fare_query(), request_id=REQUEST_ID)
    no_coverage_result = no_coverage_service.search_fares(
        fare_query(), request_id=REQUEST_ID
    )

    assert empty_result.state is ResultState.EMPTY
    assert empty_result.message != "provider raw message must not be shown"
    assert no_coverage_result.state is ResultState.NO_COVERAGE
    assert empty_result.items == no_coverage_result.items == []


def test_partial_state_requires_and_preserves_explicitly_missing_fields() -> None:
    offer = FareOffer.model_validate_json(json.dumps(fare_payload("rail_transfer")))
    partial = FareResult(
        state=ResultState.PARTIAL,
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
        request_id=OTHER_REQUEST_ID,
    )
    service = TransportService(fare_provider=FakeFareProvider(result=partial), now=lambda: NOW)

    result = service.search_fares(
        fare_query(mode="rail"), request_id=REQUEST_ID
    )

    assert result.state is ResultState.PARTIAL
    assert result.items[0].missing_fields == [
        "remaining_seats",
        "availability",
        "included_charges",
    ]


def test_no_departure_time_cannot_be_claimed_as_realtime_route_duration() -> None:
    payload = dict(route_payload())
    payload["duration_basis"] = "realtime"
    result = route_result().model_copy(
        update={"items": [RouteOption.model_validate_json(json.dumps(payload))]}
    )
    service = TransportService(route_provider=FakeRouteProvider(result=result), now=lambda: NOW)

    actual = service.search_route(route_query(mode="walking"), request_id=REQUEST_ID)

    assert actual.state is ResultState.UNAVAILABLE
    assert actual.items == []


def test_route_mode_mismatch_and_broken_source_link_are_unavailable() -> None:
    route = RouteOption.model_validate_json(
        json.dumps({**route_payload(), "mode": "taxi"})
    )
    result = route_result().model_copy(update={"items": [route]})
    service = TransportService(route_provider=FakeRouteProvider(result=result), now=lambda: NOW)

    mismatch = service.search_route(route_query(mode="walking"), request_id=REQUEST_ID)

    unlinked_route = route.model_copy(update={"source_id": "missing.source"})
    unlinked_result = result.model_copy(update={"items": [unlinked_route]})
    unlinked_service = TransportService(
        route_provider=FakeRouteProvider(result=unlinked_result), now=lambda: NOW
    )
    unlinked = unlinked_service.search_route(route_query(mode="taxi"), request_id=REQUEST_ID)

    assert mismatch.state is ResultState.UNAVAILABLE and mismatch.items == []
    assert unlinked.state is ResultState.UNAVAILABLE and unlinked.items == []


def test_route_estimate_and_missing_geometry_are_preserved_without_upgrade() -> None:
    service = TransportService(
        route_provider=FakeRouteProvider(result=route_result("taxi_estimate")),
        now=lambda: NOW,
    )

    result = service.search_route(route_query(mode="taxi"), request_id=REQUEST_ID)

    assert result.state is ResultState.DEMO
    assert result.items[0].geometry_points is None
    assert result.items[0].fare_amount_fen == 3500
    assert result.items[0].fare_evidence_state is EvidenceState.ESTIMATE
    assert result.items[0].evidence_state is EvidenceState.DEMO


def test_unexpected_provider_error_is_sanitized_to_unavailable() -> None:
    class BrokenFareProvider:
        def search_fares(self, query, *, request_id):
            raise RuntimeError("secret-token private coordinates provider html")

    service = TransportService(fare_provider=BrokenFareProvider(), now=lambda: NOW)

    result = service.search_fares(fare_query(), request_id=REQUEST_ID)

    assert result.state is ResultState.UNAVAILABLE
    assert result.items == []
    assert result.error is not None
    assert "secret-token" not in result.error.message


def test_invalid_provider_result_is_revalidated_and_not_returned() -> None:
    result = fare_result()
    invalid = result.model_copy(update={"state": ResultState.PARTIAL, "items": []})
    service = TransportService(fare_provider=FakeFareProvider(result=invalid), now=lambda: NOW)

    actual = service.search_fares(fare_query(), request_id=REQUEST_ID)

    assert actual.state is ResultState.UNAVAILABLE
    assert actual.items == []
