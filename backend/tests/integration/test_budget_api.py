from __future__ import annotations

import logging
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def make_client() -> TestClient:
    app = create_app(
        Settings(_env_file=None, env="test", allowed_origins=("http://localhost:4173",))
    )
    return TestClient(app)


def payload() -> dict[str, object]:
    return {
        "trip_id": "trip-synthetic",
        "total_budget_fen": 600000,
        "reserve_fen": 60000,
        "cost_items": [
            {
                "cost_id": "cost-synthetic",
                "category": "住宿",
                "reservation_id": "reservation-synthetic",
                "paid_fen": 200000,
                "unpaid_estimate_fen": 300000,
                "evidence_state": "user_provided",
                "completeness": "complete",
            }
        ],
    }


def test_calculate_returns_summary_and_foundation_request_id() -> None:
    response = make_client().post("/api/budget/calculate", json=payload())

    assert response.status_code == 200
    body = response.json()
    assert body["paid_total_fen"] == 200000
    assert body["known_unpaid_total_fen"] == 300000
    assert body["remaining_to_allocate_fen"] == 400000
    assert body["expected_balance_fen"] == 40000
    assert body["request_id"] == response.headers["x-request-id"]
    UUID(body["request_id"])


def test_invalid_duplicate_cost_ids_return_safe_public_error() -> None:
    data = payload()
    data["cost_items"] = [data["cost_items"][0], data["cost_items"][0]]

    response = make_client().post("/api/budget/calculate", json=data)

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "cost-synthetic" not in response.text


def test_budget_request_body_is_not_logged(caplog) -> None:
    client = make_client()
    caplog.set_level(logging.INFO, logger="app.request")
    data = payload()
    data["trip_id"] = "private-budget-sentinel"
    data["cost_items"][0]["paid_fen"] = 987654321

    response = client.post("/api/budget/calculate", json=data)

    assert response.status_code == 200
    assert "private-budget-sentinel" not in caplog.text
    assert "987654321" not in caplog.text
    assert "reservation-synthetic" not in caplog.text
    assert "request_complete" in caplog.text
