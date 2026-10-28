from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.contracts import EvidenceState, ResultState
from app.modules.weather.contracts import (
    MAX_WEATHER_DAYS,
    ProviderForecastPayload,
    WeatherDay,
    WeatherLocationMetadata,
    WeatherQuery,
)

REQUEST_ID = UUID("9d9b4bcb-07f2-484b-8e42-13692d3c5cab")
FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "weather" / "payloads.json"


def test_query_accepts_same_day_and_sixteen_day_closed_ranges() -> None:
    same_day = WeatherQuery(
        city_id="shanghai", start_date=date(2026, 10, 27), end_date=date(2026, 10, 27)
    )
    sixteen_days = WeatherQuery(
        city_id="hangzhou",
        start_date=date(2026, 10, 27),
        end_date=date(2026, 11, 11),
    )

    assert same_day.days == 1
    assert sixteen_days.days == MAX_WEATHER_DAYS == 16


@pytest.mark.parametrize(
    "kwargs",
    [
        {"city_id": "shanghai", "start_date": date(2026, 10, 28), "end_date": date(2026, 10, 27)},
        {"city_id": "shanghai", "start_date": date(2026, 10, 27), "end_date": date(2026, 11, 12)},
        {
            "city_id": "not-registered",
            "start_date": date(2026, 10, 27),
            "end_date": date(2026, 10, 27),
        },
    ],
)
def test_query_rejects_reversed_overlong_or_unknown_city_ranges(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        WeatherQuery(**kwargs)


def test_weather_day_keeps_null_distinct_from_explicit_zero() -> None:
    day = WeatherDay(
        date=date(2026, 10, 27),
        weather_code=0,
        temperature_max_c=18.0,
        temperature_min_c=8.0,
        precipitation_probability_max_pct=0.0,
        precipitation_sum_mm=0.0,
        wind_speed_10m_max_kmh=None,
    )

    assert day.precipitation_probability_max_pct == 0.0
    assert day.precipitation_sum_mm == 0.0
    assert day.wind_speed_10m_max_kmh is None
    assert "wind_speed_10m_max_kmh" in day.missing_fields
    assert "precipitation_sum_mm" not in day.missing_fields


def test_weather_day_rejects_invalid_numeric_relationships_and_duplicate_missing_fields() -> None:
    with pytest.raises(ValidationError):
        WeatherDay(
            date=date(2026, 10, 27),
            temperature_max_c=5.0,
            temperature_min_c=8.0,
        )

    with pytest.raises(ValidationError):
        WeatherDay(
            date=date(2026, 10, 27),
            temperature_max_c=18.0,
            temperature_min_c=8.0,
            missing_fields=["wind_speed_10m_max_kmh", "wind_speed_10m_max_kmh"],
        )

    with pytest.raises(ValidationError):
        WeatherDay(
            date=date(2026, 10, 27),
            precipitation_probability_max_pct=101.0,
        )


def test_weather_day_preserves_unknown_weather_code_without_guessing() -> None:
    day = WeatherDay(date=date(2026, 10, 27), weather_code=999)

    assert day.weather_code == 999
    assert day.weather_code_label == "天气现象待识别"


def test_location_metadata_uses_wgs84_and_keeps_resolved_provider_point() -> None:
    location = WeatherLocationMetadata(
        city_id="shanghai",
        requested_latitude=31.222222,
        requested_longitude=121.458056,
        resolved_latitude=31.25,
        resolved_longitude=121.5,
        elevation_m=4.0,
    )

    assert location.coordinate_system == "WGS84"
    assert location.resolved_latitude == 31.25
    assert location.requested_longitude == 121.458056


def test_fixture_payloads_validate_without_network() -> None:
    payloads = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def normalize_fixture(value: dict[str, object]) -> ProviderForecastPayload:
        data = dict(value)
        data["retrieved_at"] = datetime.fromisoformat(
            str(data["retrieved_at"]).replace("Z", "+00:00")
        )
        source = dict(data["source"])
        source["retrieved_at"] = datetime.fromisoformat(
            str(source["retrieved_at"]).replace("Z", "+00:00")
        )
        source["evidence_state"] = EvidenceState.DEMO
        data["source"] = source
        data["state"] = ResultState.DEMO
        data["days"] = [
            {**day, "date": date.fromisoformat(str(day["date"]))} for day in data["days"]
        ]
        return ProviderForecastPayload.model_validate(data)

    full = normalize_fixture(payloads["full"])
    partial = normalize_fixture(payloads["partial"])

    assert full.provider_id == "fixture.weather"
    assert full.state is ResultState.DEMO
    assert full.source.evidence_state is EvidenceState.DEMO
    assert len(full.days) == 3
    assert [day.date for day in partial.days] == [date(2026, 10, 27), date(2026, 10, 29)]
    assert partial.days[0].precipitation_sum_mm == 0.0
    assert partial.retrieved_at.tzinfo is not None


def test_provider_payload_rejects_missing_source_or_empty_days() -> None:
    with pytest.raises(ValidationError):
        ProviderForecastPayload(
            provider_id="fixture.weather",
            retrieved_at=datetime(2026, 10, 27, 0, 0, tzinfo=UTC),
            location=WeatherLocationMetadata(
                city_id="shanghai",
                requested_latitude=31.222222,
                requested_longitude=121.458056,
            ),
            days=[],
            source=None,
        )


