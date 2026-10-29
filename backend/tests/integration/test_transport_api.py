from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.contracts import EvidenceState, ResultState, SourceRef
from app.main import create_app
from app.modules.transport.contracts import FareOffer, FareResult, RouteOption, RouteResult
from app.modules.transport.providers.base import TransportProviderError
from app.modules.transport.providers.fake import (
    FakeFareProvider,
    FakeRouteProvider,
)
from app.modules.transport.service import TransportService

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "transport"
NOW = datetime(2026, 10, 28, 2, 0, tzinfo=UTC)


def fare_fixture() -> FareResult:
    payload = json.loads((FIXTURE_DIR / "fares.json").read_text(encoding="utf-8"))
    offer = FareOffer.model_validate_json(json.dumps(payload["direct_flight"]))
    source = SourceRef(
        source_id="fixture.transport.fares",
        display_name="合成票价 fixture",
        retrieved_at=NOW,
        evidence_state=EvidenceState.DEMO,
    )
    return FareResult(
        state=ResultState.DEMO,
        items=[offer],
        sources=[source],
        queried_at=NOW,
        request_id=uuid4(),
    )


def route_fixture() -> RouteResult:
    payload = json.loads((FIXTURE_DIR / "routes.json").read_text(encoding="utf-8"))
    route = RouteOption.model_validate_json(json.dumps(payload["walking_route"]))
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
        request_id=uuid4(),
    )


def make_client(*, fare_provider=None, route_provider=None) -> TestClient:
    app = create_app(
        Settings(_env_file=None, env="test", allowed_origins=("http://localhost:4173",))
    )
    app.state.transport_service = TransportService(
        fare_provider=fare_provider,
        route_provider=route_provider,
        now=lambda: NOW,
    )
    return TestClient(app)


def fare_query_payload() -> dict[str, object]:
    return {
        "origin": {"display_name": "上海虹桥"},
        "destination": {"display_name": "杭州萧山"},
        "mode": "flight",
        "travel_date": "2026-11-10",
        "passenger_count": 2,
    }


def route_query_payload(mode: str = "walking") -> dict[str, object]:
    return {
        "origin": {"display_name": "起点 A"},
        "destination": {"display_name": "目的地 B"},
        "mode": mode,
    }


def test_fare_search_returns_contract_result_and_request_id() -> None:
    response = make_client(fare_provider=FakeFareProvider(result=fare_fixture())).post(
        "/api/transport/fares/search", json=fare_query_payload()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "demo"
    assert body["items"][0]["travel_date"] == "2026-11-10"
    assert body["items"][0]["price_basis"] == "per_passenger"
    assert body["items"][0]["remaining_seats"] is None
    assert body["request_id"] == response.headers["x-request-id"]


def test_route_search_returns_geometry_only_when_provider_supplied_it() -> None:
    response = make_client(route_provider=FakeRouteProvider(result=route_fixture())).post(
        "/api/transport/routes/search", json=route_query_payload()
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "demo"
    assert len(body["items"][0]["geometry_points"]) == 2
    assert body["items"][0]["fare_amount_fen"] is None


def test_default_transport_services_are_unconfigured_and_do_not_return_fixture_data() -> None:
    client = make_client()

    fare = client.post("/api/transport/fares/search", json=fare_query_payload())
    route = client.post("/api/transport/routes/search", json=route_query_payload("transit"))

    assert fare.status_code == route.status_code == 200
    assert fare.json()["state"] == route.json()["state"] == "unconfigured"
    assert fare.json()["items"] == route.json()["items"] == []
    assert fare.json()["error"]["code"] == route.json()["error"]["code"] == "UNCONFIGURED"


def test_route_provider_failure_is_an_empty_public_state_with_matching_request_id() -> None:
    provider = FakeRouteProvider(error=TransportProviderError("rate_limited"))
    response = make_client(route_provider=provider).post(
        "/api/transport/routes/search", json=route_query_payload("taxi")
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "rate_limited"
    assert body["items"] == []
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["request_id"] == body["request_id"]
    assert response.headers["x-request-id"] == body["request_id"]


def test_fare_search_forwards_optional_child_count_to_provider() -> None:
    provider = FakeFareProvider(result=fare_fixture())
    payload = fare_query_payload()
    payload["passenger_count"] = 3
    payload["child_count"] = 1

    response = make_client(fare_provider=provider).post(
        "/api/transport/fares/search", json=payload
    )

    assert response.status_code == 200
    assert provider.calls[0].query.passenger_count == 3
    assert provider.calls[0].query.child_count == 1


def test_invalid_transport_body_is_rejected_before_provider_call() -> None:
    provider = FakeFareProvider(result=fare_fixture())
    payload = fare_query_payload()
    payload["passenger_count"] = 1.5
    payload["unexpected"] = "private-sentinel"

    response = make_client(fare_provider=provider).post(
        "/api/transport/fares/search", json=payload
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert provider.calls == []
    assert "private-sentinel" not in response.text
    assert response.headers["x-request-id"] == response.json()["request_id"]


def test_transport_request_body_is_not_written_to_request_log(caplog) -> None:
    client = make_client()
    caplog.set_level(logging.INFO, logger="app.request")
    payload = fare_query_payload()
    payload["origin"] = {"display_name": "private-origin-sentinel"}
    payload["destination"] = {"display_name": "private-destination-sentinel"}

    response = client.post("/api/transport/fares/search", json=payload)

    assert response.status_code == 200
    assert "private-origin-sentinel" not in caplog.text
    assert "private-destination-sentinel" not in caplog.text
    assert "request_complete" in caplog.text


def test_transport_cors_rejects_non_allowlisted_origin() -> None:
    response = make_client().post(
        "/api/transport/routes/search",
        headers={"Origin": "http://evil.example"},
        json=route_query_payload(),
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
