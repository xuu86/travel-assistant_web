from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.contracts import EvidenceState, ResultState
from app.main import create_app
from app.modules.weather.contracts import ProviderForecastPayload
from app.modules.weather.providers.base import FakeWeatherProvider
from app.modules.weather.service import WeatherService

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "weather" / "payloads.json"


def load_payload(name: str) -> ProviderForecastPayload:
    value = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))[name]
    data = dict(value)
    data["retrieved_at"] = datetime.fromisoformat(str(data["retrieved_at"]).replace("Z", "+00:00"))
    source = dict(data["source"])
    source["retrieved_at"] = datetime.fromisoformat(
        str(source["retrieved_at"]).replace("Z", "+00:00")
    )
    source["evidence_state"] = EvidenceState.DEMO
    data["source"] = source
    data["state"] = ResultState.DEMO
    data["days"] = [{**day, "date": date.fromisoformat(str(day["date"]))} for day in data["days"]]
    return ProviderForecastPayload.model_validate(data)


def make_app(provider=None):
    application = create_app(
        Settings(_env_file=None, env="test", allowed_origins=("http://localhost:4173",))
    )
    application.state.weather_service = WeatherService(
        provider,
        today=lambda: date(2026, 10, 27),
    )
    return application


def test_forecast_returns_fake_complete_payload_with_coverage() -> None:
    client = TestClient(make_app(FakeWeatherProvider(payload=load_payload("full"))))

    response = client.post(
        "/api/weather/forecast",
        json={"city_id": "shanghai", "start_date": "2026-10-27", "end_date": "2026-10-29"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "demo"
    assert [item["date"] for item in body["items"]] == [
        "2026-10-27",
        "2026-10-28",
        "2026-10-29",
    ]
    assert body["coverage"]["missing"] == []
    assert body["location"]["coordinate_system"] == "WGS84"
    assert response.headers["x-request-id"] == body["request_id"]


def test_default_service_is_unconfigured_and_does_not_return_demo() -> None:
    client = TestClient(make_app())

    response = client.post(
        "/api/weather/forecast",
        json={"city_id": "shanghai", "start_date": "2026-10-27", "end_date": "2026-10-27"},
    )

    assert response.status_code == 200
    assert response.json()["state"] == "unconfigured"
    assert response.json()["items"] == []


def test_invalid_city_or_seventeen_day_range_is_rejected_before_provider_call() -> None:
    provider = FakeWeatherProvider(payload=load_payload("full"))
    client = TestClient(make_app(provider))

    unknown = client.post(
        "/api/weather/forecast",
        json={"city_id": "unknown", "start_date": "2026-10-27", "end_date": "2026-10-27"},
    )
    overlong = client.post(
        "/api/weather/forecast",
        json={"city_id": "shanghai", "start_date": "2026-10-27", "end_date": "2026-11-12"},
    )

    assert unknown.status_code == 422
    assert overlong.status_code == 422
    assert provider.calls == []
    assert unknown.json()["code"] == "VALIDATION_ERROR"
    assert overlong.json()["code"] == "VALIDATION_ERROR"


def test_provider_failure_preserves_public_error_and_request_id() -> None:
    provider = FakeWeatherProvider(
        error=__import__(
            "app.modules.weather.providers.base", fromlist=["WeatherProviderError"]
        ).WeatherProviderError("rate_limited")
    )
    client = TestClient(make_app(provider))

    response = client.post(
        "/api/weather/forecast",
        json={"city_id": "shanghai", "start_date": "2026-10-27", "end_date": "2026-10-27"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "rate_limited"
    assert body["error"]["code"] == "RATE_LIMITED"
    assert body["error"]["request_id"] == body["request_id"]
    assert response.headers["x-request-id"] == body["request_id"]


def test_request_body_sentinel_is_not_written_to_request_log(caplog) -> None:
    client = TestClient(make_app())
    caplog.set_level(logging.INFO, logger="app.request")
    sentinel = "private-trip-sentinel"

    response = client.post(
        "/api/weather/forecast",
        json={
            "city_id": "shanghai",
            "start_date": "2026-10-27",
            "end_date": "2026-10-27",
            "note": sentinel,
        },
    )

    assert response.status_code == 422
    assert sentinel not in caplog.text
    assert "request_complete" in caplog.text


def test_cors_rejects_non_allowlisted_origin() -> None:
    client = TestClient(make_app())

    response = client.post(
        "/api/weather/forecast",
        headers={"Origin": "http://evil.example"},
        json={"city_id": "shanghai", "start_date": "2026-10-27", "end_date": "2026-10-27"},
    )

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
