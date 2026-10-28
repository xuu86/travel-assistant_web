from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.contracts import EvidenceState, ResultState, SourceRef
from app.modules.transport.contracts import (
    ChargeComponent,
    FareOffer,
    FareQuery,
    FareResult,
    FareSegment,
    GeometryPoint,
    PlaceRef,
    RouteOption,
    RouteQuery,
    RouteResult,
    RouteStep,
)

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "transport"
REQUEST_ID = UUID("367f478a-b1be-4f53-9248-befb40dc21a2")
NOW = datetime(2026, 10, 28, 2, 0, tzinfo=UTC)


def fare_data(name: str = "direct_flight") -> dict[str, object]:
    payloads = json.loads((FIXTURE_DIR / "fares.json").read_text(encoding="utf-8"))
    return payloads[name]


def route_data(name: str = "walking_route") -> dict[str, object]:
    payloads = json.loads((FIXTURE_DIR / "routes.json").read_text(encoding="utf-8"))
    return payloads[name]


def fare_offer(name: str = "direct_flight") -> FareOffer:
    return FareOffer.model_validate_json(json.dumps(fare_data(name)))


def route_option(name: str = "walking_route") -> RouteOption:
    return RouteOption.model_validate_json(json.dumps(route_data(name)))


def source(*, evidence_state: EvidenceState = EvidenceState.DEMO) -> SourceRef:
    return SourceRef(
        source_id="fixture.transport.fares",
        display_name="合成交通 fixture",
        retrieved_at=NOW,
        evidence_state=evidence_state,
    )


def test_place_ref_accepts_name_only_or_complete_wgs84_coordinates() -> None:
    name_only = PlaceRef(display_name="上海虹桥站")
    with_coordinates = PlaceRef(
        place_id="station.shanghai-hongqiao",
        display_name="上海虹桥站",
        latitude=31.1979,
        longitude=121.3363,
    )

    assert name_only.latitude is None and name_only.longitude is None
    assert with_coordinates.coordinate_system == "WGS84"
    assert with_coordinates.place_id == "station.shanghai-hongqiao"


@pytest.mark.parametrize(
    "payload",
    [
        {"display_name": "   "},
        {"display_name": "起点", "latitude": 31.2},
        {"display_name": "起点", "longitude": 121.4},
        {"display_name": "起点", "latitude": 91.0, "longitude": 121.4},
        {"display_name": "起点", "latitude": 31.2, "longitude": 181.0},
        {"display_name": "起点", "latitude": float("nan"), "longitude": 121.4},
        {"display_name": "起点", "latitude": 31.2, "longitude": 121.4, "extra": True},
    ],
)
def test_place_ref_rejects_empty_or_invalid_coordinates_and_extra_fields(
    payload: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        PlaceRef.model_validate(payload)


def test_fare_query_requires_explicit_date_and_keeps_target_travel_day() -> None:
    query = FareQuery.model_validate_json(
        json.dumps(
            {
                "origin": {"display_name": "上海虹桥"},
                "destination": {"display_name": "杭州东"},
                "mode": "rail",
                "travel_date": "2026-11-10",
                "passenger_count": 2,
            }
        )
    )

    assert query.travel_date == date(2026, 11, 10)
    assert query.passenger_count == 2


@pytest.mark.parametrize(
    "override",
    [
        {"mode": "bus"},
        {"travel_date": None},
        {"passenger_count": 0},
        {"passenger_count": True},
        {"passenger_count": 1.5},
        {"extra": "unexpected"},
    ],
)
def test_fare_query_rejects_invalid_mode_date_passengers_and_extra_fields(
    override: dict[str, object],
) -> None:
    payload: dict[str, object] = {
        "origin": {"display_name": "上海虹桥"},
        "destination": {"display_name": "杭州东"},
        "mode": "flight",
        "travel_date": date(2026, 11, 10),
        "passenger_count": 1,
    }
    payload.update(override)

    with pytest.raises(ValidationError):
        FareQuery.model_validate(payload)


def test_fare_query_rejects_same_place_but_does_not_bind_to_itinerary_date() -> None:
    with pytest.raises(ValidationError):
        FareQuery(
            origin=PlaceRef(place_id="station.a", display_name="甲站"),
            destination=PlaceRef(place_id="station.a", display_name="甲站（别名）"),
            mode="rail",
            travel_date=date(2026, 11, 10),
            passenger_count=1,
        )

    query = FareQuery(
        origin=PlaceRef(display_name="上海虹桥"),
        destination=PlaceRef(display_name="杭州东"),
        mode="flight",
        travel_date=date(2026, 11, 10),
        passenger_count=1,
    )
    assert query.travel_date != date(2026, 10, 28)


def test_fare_segment_normalizes_timezone_aware_datetimes_to_utc() -> None:
    segment = FareSegment.model_validate_json(json.dumps(fare_data()["segments"][0]))

    assert segment.departure_at == datetime(2026, 11, 10, 0, 0, tzinfo=UTC)
    assert segment.arrival_at == datetime(2026, 11, 10, 1, 10, tzinfo=UTC)
    assert segment.departure_timezone == "Asia/Shanghai"


@pytest.mark.parametrize(
    "override",
    [
        {"departure_at": datetime(2026, 11, 10, 8, 0)},
        {"departure_timezone": "Not/A-Timezone"},
        {"departure_at": "2026-11-10T08:00:00"},
    ],
)
def test_segment_rejects_naive_time_or_invalid_iana_timezone(override: dict[str, object]) -> None:
    payload = dict(fare_data()["segments"][0])
    payload.update(override)
    with pytest.raises(ValidationError):
        FareSegment.model_validate(payload)


def test_fare_offer_preserves_zero_null_and_provider_segment_order() -> None:
    offer = fare_offer()
    transfer = fare_offer("rail_transfer")

    assert offer.price_fen == 128000
    assert offer.included_charges[0].amount_fen == 0
    assert offer.remaining_seats is None
    assert [segment.segment_id for segment in transfer.segments] == [
        "rail-segment-001",
        "rail-segment-002",
    ]
    assert transfer.service_number is None
    assert transfer.price_scope == "entire_journey"
    assert transfer.departure_at == transfer.segments[0].departure_at
    assert transfer.arrival_at == transfer.segments[-1].arrival_at


@pytest.mark.parametrize("invalid_amount", [-1, 1.5, True])
def test_fare_offer_rejects_negative_float_or_boolean_money(invalid_amount: object) -> None:
    payload = dict(fare_data())
    payload["price_fen"] = invalid_amount
    with pytest.raises(ValidationError):
        FareOffer.model_validate(payload)


def test_fare_offer_rejects_non_cny_integer_amount() -> None:
    payload = dict(fare_data())
    payload["currency_code"] = "USD"
    with pytest.raises(ValidationError):
        FareOffer.model_validate_json(json.dumps(payload))


def test_fare_offer_requires_unknown_nullable_facts_to_be_marked_missing() -> None:
    payload = dict(fare_data())
    payload["missing_fields"] = []
    with pytest.raises(ValidationError):
        FareOffer.model_validate_json(json.dumps(payload))

    payload = fare_data("rail_transfer")
    payload["missing_fields"] = ["remaining_seats", "availability"]
    with pytest.raises(ValidationError):
        FareOffer.model_validate_json(json.dumps(payload))


def test_fare_offer_rejects_multi_segment_single_service_and_wrong_top_level_times() -> None:
    payload = dict(fare_data("rail_transfer"))
    payload["service_number"] = "G-FAKE-COMBINED"
    with pytest.raises(ValidationError):
        FareOffer.model_validate_json(json.dumps(payload))


def test_single_segment_price_must_identify_the_segment_it_covers() -> None:
    payload = dict(fare_data("rail_transfer"))
    payload["price_scope"] = "single_segment"
    payload["price_segment_id"] = "rail-segment-002"
    offer = FareOffer.model_validate_json(json.dumps(payload))
    assert offer.price_segment_id == "rail-segment-002"

    payload["price_segment_id"] = "unknown-segment"
    with pytest.raises(ValidationError):
        FareOffer.model_validate_json(json.dumps(payload))

    payload = dict(fare_data())
    payload["arrival_at"] = "2026-11-10T11:00:00+08:00"
    with pytest.raises(ValidationError):
        FareOffer.model_validate_json(json.dumps(payload))


def test_charge_component_requires_nonnegative_cny_amount_and_explicit_status() -> None:
    charge = ChargeComponent(
        charge_type="baggage",
        display_name="行李费",
        inclusion_state="unknown",
        amount_fen=None,
        currency_code="CNY",
        amount_basis="unknown",
    )
    assert charge.amount_fen is None

    with pytest.raises(ValidationError):
        ChargeComponent(
            charge_type="tax",
            display_name="税费",
            inclusion_state="included",
            amount_fen=-1,
            currency_code="CNY",
            amount_basis="per_passenger",
        )


def test_route_query_requires_one_explicit_mode_and_utc_normalizes_departure() -> None:
    query = RouteQuery(
        origin=PlaceRef(display_name="起点 A"),
        destination=PlaceRef(display_name="目的地 B"),
        mode="transit",
        depart_at=datetime.fromisoformat("2026-11-10T08:00:00+08:00"),
    )

    assert query.depart_at == datetime(2026, 11, 10, 0, 0, tzinfo=UTC)

    same_endpoint_query = RouteQuery(
        origin=PlaceRef(display_name="同一地点"),
        destination=PlaceRef(display_name="同一地点"),
        mode="walking",
    )
    assert same_endpoint_query.mode == "walking"

    with pytest.raises(ValidationError):
        RouteQuery(
            origin=PlaceRef(display_name="起点 A"),
            destination=PlaceRef(display_name="目的地 B"),
            mode="cycling",
        )
    with pytest.raises(ValidationError):
        RouteQuery(
            origin=PlaceRef(display_name="起点 A"),
            destination=PlaceRef(display_name="目的地 B"),
            mode="walking",
            depart_at=datetime(2026, 11, 10, 8, 0),
        )


def test_route_step_and_geometry_validate_coordinate_pairs_and_bounds() -> None:
    valid_step = route_data()["steps"][0]
    step = RouteStep.model_validate(valid_step)
    assert step.coordinate_system == "WGS84"

    with pytest.raises(ValidationError):
        RouteStep.model_validate({**valid_step, "end_longitude": None})
    with pytest.raises(ValidationError):
        GeometryPoint(latitude=91.0, longitude=121.4)
    with pytest.raises(ValidationError):
        GeometryPoint(latitude=31.2, longitude=float("inf"))


def test_route_option_distinguishes_unknown_fare_from_explicit_zero_and_estimate() -> None:
    walking = route_option()
    taxi = route_option("taxi_estimate")

    assert walking.fare_amount_fen is None
    assert walking.fare_basis == "unknown"
    assert taxi.fare_amount_fen == 3500
    assert taxi.fare_basis == "meter_estimate"
    assert taxi.fare_evidence_state is EvidenceState.ESTIMATE
    assert taxi.geometry_points is None


def test_route_option_rejects_duration_basis_and_fare_semantic_conflicts() -> None:
    payload = dict(route_data("taxi_estimate"))
    payload["duration_basis"] = "realtime"
    with pytest.raises(ValidationError):
        RouteOption.model_validate_json(json.dumps(payload))

    payload = dict(route_data("taxi_estimate"))
    payload["duration_seconds"] = 10
    with pytest.raises(ValidationError):
        RouteOption.model_validate_json(json.dumps(payload))

    payload = dict(route_data("taxi_estimate"))
    payload["fare_amount_fen"] = None
    payload["fare_basis"] = "per_route"
    payload["fare_evidence_state"] = "unknown"
    with pytest.raises(ValidationError):
        RouteOption.model_validate_json(json.dumps(payload))

    payload = dict(route_data("taxi_estimate"))
    payload["fare_evidence_state"] = "verified"
    with pytest.raises(ValidationError):
        RouteOption.model_validate_json(json.dumps(payload))


def test_geometry_if_present_has_at_least_two_wgs84_points() -> None:
    payload = dict(route_data())
    payload["geometry_points"] = [route_data()["geometry_points"][0]]
    with pytest.raises(ValidationError):
        RouteOption.model_validate_json(json.dumps(payload))


def test_route_option_requires_unknown_facts_to_be_marked_missing() -> None:
    payload = dict(route_data())
    payload["missing_fields"] = []
    with pytest.raises(ValidationError):
        RouteOption.model_validate_json(json.dumps(payload))


def test_fare_result_enforces_source_link_state_and_partial_fields() -> None:
    offer = fare_offer()
    result = FareResult(
        state=ResultState.PARTIAL,
        items=[offer],
        sources=[source()],
        queried_at=NOW,
        request_id=REQUEST_ID,
        message="部分字段待核实",
    )
    assert result.items[0].source_id == result.sources[0].source_id

    with pytest.raises(ValidationError):
        FareResult(
            state=ResultState.PARTIAL,
            items=[],
            sources=[source()],
            queried_at=NOW,
            request_id=REQUEST_ID,
        )

    unlinked = FareOffer.model_validate_json(
        json.dumps({**fare_data(), "source_id": "missing.source"})
    )
    with pytest.raises(ValidationError):
        FareResult(
            state=ResultState.LIVE,
            items=[unlinked],
            sources=[source(evidence_state=EvidenceState.VERIFIED)],
            queried_at=NOW,
            request_id=REQUEST_ID,
        )


def test_live_result_cannot_upgrade_demo_source_or_demo_offer() -> None:
    offer = fare_offer()
    with pytest.raises(ValidationError):
        FareResult(
            state=ResultState.LIVE,
            items=[offer],
            sources=[source(evidence_state=EvidenceState.VERIFIED)],
            queried_at=NOW,
            request_id=REQUEST_ID,
        )

    with pytest.raises(ValidationError):
        FareResult(
            state=ResultState.LIVE,
            items=[offer],
            sources=[source()],
            queried_at=NOW,
            request_id=REQUEST_ID,
        )


def test_route_result_requires_source_association_and_nonempty_partial_items() -> None:
    route = route_option()
    result = RouteResult(
        state=ResultState.PARTIAL,
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
        request_id=REQUEST_ID,
        message="路线缺少部分字段",
    )
    assert result.items[0].route_id == "fixture-walk-001"

    with pytest.raises(ValidationError):
        RouteResult(
            state=ResultState.LIVE,
            items=[route],
            sources=[],
            queried_at=NOW,
            request_id=REQUEST_ID,
        )
