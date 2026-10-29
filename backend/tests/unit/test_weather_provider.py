from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pytest

from app.core.cities import get_city
from app.core.contracts import EvidenceState, ResultState
from app.modules.weather.contracts import ProviderForecastPayload, WeatherQuery
from app.modules.weather.providers.base import (
    FakeWeatherProvider,
    WeatherProviderError,
    select_provider,
)
from app.modules.weather.providers.open_meteo import OpenMeteoWeatherProvider

FIXTURE_PATH = Path(__file__).parents[1] / "fixtures" / "weather" / "payloads.json"


def load_payload() -> ProviderForecastPayload:
    value = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["full"]
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


def test_default_selection_is_unconfigured_and_does_not_create_demo_data() -> None:
    assert select_provider(None) is None
    assert select_provider("") is None
    assert select_provider("unconfigured") is None


def test_fake_provider_is_only_returned_when_explicitly_selected() -> None:
    fake = FakeWeatherProvider(payload=load_payload())

    selected = select_provider("fixture.weather", fake=fake)

    assert selected is fake
    assert selected.provider_id == "fixture.weather"


def test_fake_provider_records_query_and_returns_explicit_demo_payload() -> None:
    fake = FakeWeatherProvider(payload=load_payload())
    city = get_city("shanghai")
    assert city is not None
    query = WeatherQuery(
        city_id="shanghai",
        start_date=date(2026, 10, 27),
        end_date=date(2026, 10, 29),
    )

    result = fake.fetch(city, query)

    assert result.state is ResultState.DEMO
    assert result.source.evidence_state is EvidenceState.DEMO
    assert fake.calls == [fake.calls[0]]
    assert fake.calls[0].city_id == "shanghai"
    assert fake.calls[0].start_date == "2026-10-27"
    assert fake.calls[0].end_date == "2026-10-29"


def test_fake_provider_error_is_explicit_and_never_returns_demo_payload() -> None:
    fake = FakeWeatherProvider(error=WeatherProviderError("unavailable"))
    city = get_city("hangzhou")
    assert city is not None
    query = WeatherQuery(
        city_id="hangzhou",
        start_date=date(2026, 10, 27),
        end_date=date(2026, 10, 27),
    )

    with pytest.raises(WeatherProviderError, match="weather provider unavailable"):
        fake.fetch(city, query)

    assert len(fake.calls) == 1


def test_unknown_provider_is_not_silently_replaced() -> None:
    with pytest.raises(WeatherProviderError, match="not registered"):
        select_provider("some-unknown-provider")


def test_open_meteo_is_selected_only_when_explicitly_configured() -> None:
    assert isinstance(select_provider("open_meteo"), OpenMeteoWeatherProvider)

