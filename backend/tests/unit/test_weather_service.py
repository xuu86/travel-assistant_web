from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

import pytest

from app.core.contracts import ErrorCode, EvidenceState, ResultState
from app.modules.weather.contracts import ProviderForecastPayload, WeatherQuery
from app.modules.weather.providers.base import FakeWeatherProvider, WeatherProviderError
from app.modules.weather.service import WeatherService

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "weather" / "payloads.json"
REQUEST_ID = UUID("9d9b4bcb-07f2-484b-8e42-13692d3c5cab")


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


def query(city_id: str, start: date, end: date) -> WeatherQuery:
    return WeatherQuery(city_id=city_id, start_date=start, end_date=end)


def test_complete_fixture_returns_demo_state_and_complete_coverage() -> None:
    fake = FakeWeatherProvider(payload=load_payload("full"))
    service = WeatherService(fake, today=lambda: date(2026, 10, 27))

    result = service.forecast(
        query("shanghai", date(2026, 10, 27), date(2026, 10, 29)),
        request_id=REQUEST_ID,
    )

    assert result.state is ResultState.DEMO
    assert [item.date for item in result.items] == [
        date(2026, 10, 27),
        date(2026, 10, 28),
        date(2026, 10, 29),
    ]
    assert result.coverage is not None
    assert result.coverage.covered[0].start == date(2026, 10, 27)
    assert result.coverage.covered[0].end == date(2026, 10, 29)
    assert result.coverage.missing == []
    assert result.request_id == REQUEST_ID


def test_partial_fixture_splits_covered_and_missing_dates_without_filling_gap() -> None:
    fake = FakeWeatherProvider(payload=load_payload("partial"))
    service = WeatherService(fake, today=lambda: date(2026, 10, 27))

    result = service.forecast(
        query("hangzhou", date(2026, 10, 27), date(2026, 10, 29)),
        request_id=REQUEST_ID,
    )

    assert result.state is ResultState.DEMO
    assert [item.date for item in result.items] == [date(2026, 10, 27), date(2026, 10, 29)]
    assert result.coverage is not None
    assert [(item.start, item.end) for item in result.coverage.covered] == [
        (date(2026, 10, 27), date(2026, 10, 27)),
        (date(2026, 10, 29), date(2026, 10, 29)),
    ]
    assert [(item.start, item.end) for item in result.coverage.missing] == [
        (date(2026, 10, 28), date(2026, 10, 28)),
    ]


def test_past_dates_are_missing_and_do_not_call_provider() -> None:
    fake = FakeWeatherProvider(payload=load_payload("full"))
    service = WeatherService(fake, today=lambda: date(2026, 10, 27))

    result = service.forecast(
        query("shanghai", date(2026, 10, 25), date(2026, 10, 26)),
        request_id=REQUEST_ID,
    )

    assert result.state is ResultState.NO_COVERAGE
    assert result.items == []
    assert fake.calls == []
    assert result.coverage is not None
    assert [(item.start, item.end) for item in result.coverage.missing] == [
        (date(2026, 10, 25), date(2026, 10, 26)),
    ]


def test_mixed_past_and_future_only_sends_future_range_to_provider() -> None:
    fake = FakeWeatherProvider(payload=load_payload("full"))
    service = WeatherService(fake, today=lambda: date(2026, 10, 27))

    result = service.forecast(
        query("shanghai", date(2026, 10, 26), date(2026, 10, 29)),
        request_id=REQUEST_ID,
    )

    assert result.state is ResultState.DEMO
    assert fake.calls[0].start_date == "2026-10-27"
    assert fake.calls[0].end_date == "2026-10-29"
    assert result.coverage is not None
    assert result.coverage.missing[0].start == date(2026, 10, 26)


@pytest.mark.parametrize(
    ("provider_status", "expected_state", "expected_code"),
    [
        ("unavailable", ResultState.UNAVAILABLE, ErrorCode.PROVIDER_UNAVAILABLE),
        ("rate_limited", ResultState.RATE_LIMITED, ErrorCode.RATE_LIMITED),
        ("policy_unavailable", ResultState.POLICY_UNAVAILABLE, ErrorCode.POLICY_UNAVAILABLE),
    ],
)
def test_provider_failures_map_to_public_states_without_payload(
    provider_status, expected_state, expected_code
) -> None:
    fake = FakeWeatherProvider(error=WeatherProviderError(provider_status))
    service = WeatherService(fake, today=lambda: date(2026, 10, 27))

    result = service.forecast(
        query("shanghai", date(2026, 10, 27), date(2026, 10, 27)),
        request_id=REQUEST_ID,
    )

    assert result.state is expected_state
    assert result.items == []
    assert result.coverage is None
    assert result.error is not None
    assert result.error.code is expected_code
    assert result.error.request_id == REQUEST_ID


def test_unconfigured_provider_is_honest_and_does_not_create_demo_data() -> None:
    service = WeatherService(None, today=lambda: date(2026, 10, 27))

    result = service.forecast(
        query("shanghai", date(2026, 10, 27), date(2026, 10, 27)),
        request_id=REQUEST_ID,
    )

    assert result.state is ResultState.UNCONFIGURED
    assert result.items == []
    assert result.coverage is None
    assert result.error is not None
    assert result.error.code is ErrorCode.UNCONFIGURED

