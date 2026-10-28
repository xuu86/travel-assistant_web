from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest

from app.core.cities import get_city
from app.core.contracts import EvidenceState, ResultState, SourceRef
from app.modules.weather.contracts import (
    ProviderForecastPayload,
    WeatherDay,
    WeatherLocationMetadata,
    WeatherQuery,
)
from app.modules.weather.providers.base import WeatherProviderError
from app.modules.weather.runtime import (
    CACHE_TTL,
    MAX_RETRIES,
    REQUEST_TIMEOUT_SECONDS,
    WeatherRuntime,
)


@dataclass
class SequenceProvider:
    responses: list[object]
    provider_id: str = "fixture.live"
    calls: int = 0

    def fetch(self, city, query):
        self.calls += 1
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def live_payload(retrieved_at: datetime) -> ProviderForecastPayload:
    return ProviderForecastPayload(
        provider_id="fixture.live",
        state=ResultState.LIVE,
        retrieved_at=retrieved_at,
        source=SourceRef(
            source_id="fixture.live",
            display_name="Live fixture",
            url="https://fixture.example/live",
            retrieved_at=retrieved_at,
            evidence_state=EvidenceState.VERIFIED,
        ),
        location=WeatherLocationMetadata(
            city_id="shanghai",
            requested_latitude=31.222222,
            requested_longitude=121.458056,
        ),
        days=[
            WeatherDay(
                date=date(2026, 10, 27),
                weather_code=1,
                temperature_max_c=20.0,
                temperature_min_c=13.0,
                precipitation_probability_max_pct=0.0,
                precipitation_sum_mm=0.0,
                wind_speed_10m_max_kmh=10.0,
            )
        ],
    )


def test_runtime_constants_match_approved_plan() -> None:
    assert MAX_RETRIES == 1
    assert REQUEST_TIMEOUT_SECONDS == 8.0
    assert CACHE_TTL == timedelta(minutes=15)


def test_transient_error_retries_once_and_succeeds() -> None:
    retrieved = datetime(2026, 10, 27, 0, 0, tzinfo=UTC)
    provider = SequenceProvider(responses=[WeatherProviderError("503"), live_payload(retrieved)])
    runtime = WeatherRuntime(provider)
    city = get_city("shanghai")
    assert city is not None
    query = WeatherQuery(
        city_id="shanghai",
        start_date=date(2026, 10, 27),
        end_date=date(2026, 10, 27),
    )

    result = runtime.fetch(city, query)

    assert result.retrieved_at == retrieved
    assert provider.calls == 2


def test_non_transient_error_does_not_retry() -> None:
    provider = SequenceProvider(responses=[WeatherProviderError("429")])
    runtime = WeatherRuntime(provider)
    city = get_city("shanghai")
    assert city is not None
    query = WeatherQuery(
        city_id="shanghai",
        start_date=date(2026, 10, 27),
        end_date=date(2026, 10, 27),
    )

    with pytest.raises(WeatherProviderError):
        runtime.fetch(city, query)

    assert provider.calls == 1


def test_second_transient_error_stops_at_one_retry() -> None:
    provider = SequenceProvider(
        responses=[WeatherProviderError("timeout"), WeatherProviderError("504")]
    )
    runtime = WeatherRuntime(provider)
    city = get_city("shanghai")
    assert city is not None
    query = WeatherQuery(
        city_id="shanghai",
        start_date=date(2026, 10, 27),
        end_date=date(2026, 10, 27),
    )

    with pytest.raises(WeatherProviderError):
        runtime.fetch(city, query)

    assert provider.calls == 2


def test_live_payload_is_cached_until_ttl_then_refetched() -> None:
    current = [datetime(2026, 10, 27, 0, 0, tzinfo=UTC)]
    retrieved = datetime(2026, 10, 27, 0, 0, tzinfo=UTC)
    first = live_payload(retrieved)
    second = live_payload(datetime(2026, 10, 27, 0, 16, tzinfo=UTC))
    provider = SequenceProvider(responses=[first, second])
    runtime = WeatherRuntime(provider, now=lambda: current[0])
    city = get_city("shanghai")
    assert city is not None
    query = WeatherQuery(
        city_id="shanghai",
        start_date=date(2026, 10, 27),
        end_date=date(2026, 10, 27),
    )

    cached = runtime.fetch(city, query)
    current[0] += timedelta(minutes=14, seconds=59)
    still_cached = runtime.fetch(city, query)
    current[0] += timedelta(seconds=1)
    refreshed = runtime.fetch(city, query)

    assert cached.retrieved_at == retrieved
    assert still_cached.retrieved_at == retrieved
    assert refreshed.retrieved_at == datetime(2026, 10, 27, 0, 16, tzinfo=UTC)
    assert provider.calls == 2


def test_expired_cache_does_not_return_stale_result_on_error() -> None:
    current = [datetime(2026, 10, 27, 0, 0, tzinfo=UTC)]
    provider = SequenceProvider(
        responses=[
            live_payload(current[0]),
            WeatherProviderError("503"),
            WeatherProviderError("503"),
        ]
    )
    runtime = WeatherRuntime(provider, now=lambda: current[0])
    city = get_city("shanghai")
    assert city is not None
    query = WeatherQuery(
        city_id="shanghai",
        start_date=date(2026, 10, 27),
        end_date=date(2026, 10, 27),
    )

    runtime.fetch(city, query)
    current[0] += CACHE_TTL

    with pytest.raises(WeatherProviderError):
        runtime.fetch(city, query)

    assert provider.calls == 3
