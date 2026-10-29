from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from app.core.cities import get_city
from app.modules.weather.contracts import WeatherQuery
from app.modules.weather.providers.base import WeatherProviderError, select_provider
from app.modules.weather.providers.open_meteo import (
    DAILY_VARIABLES,
    FORECAST_URL,
    MAX_RESPONSE_BYTES,
    OpenMeteoWeatherProvider,
)


def _response_payload() -> dict[str, object]:
    return {
        "latitude": 31.25,
        "longitude": 121.5,
        "elevation": 12.0,
        "daily": {
            "time": ["2026-10-29", "2026-10-30"],
            "weather_code": [1, 61],
            "temperature_2m_max": [21.5, 19.0],
            "temperature_2m_min": [14.0, 12.0],
            "precipitation_probability_max": [0, 80],
            "precipitation_sum": [0, 4.2],
            "wind_speed_10m_max": [10, 15],
        },
    }


def _provider(handler) -> OpenMeteoWeatherProvider:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return OpenMeteoWeatherProvider(timeout_seconds=3, client=client)


def _query() -> WeatherQuery:
    return WeatherQuery(
        city_id="shanghai",
        start_date=date(2026, 10, 29),
        end_date=date(2026, 10, 30),
    )


def test_registered_provider_is_selectable_without_api_key() -> None:
    selected = select_provider("open_meteo")
    assert isinstance(selected, OpenMeteoWeatherProvider)
    assert selected.timeout_seconds == 8.0


def test_request_uses_fixed_endpoint_city_coordinates_local_dates_and_metric_units() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(FORECAST_URL)
        params = dict(request.url.params)
        assert params["latitude"] == "31.222222"
        assert params["longitude"] == "121.458056"
        assert params["daily"] == ",".join(DAILY_VARIABLES)
        assert params["timezone"] == "Asia/Shanghai"
        assert params["temperature_unit"] == "celsius"
        assert params["precipitation_unit"] == "mm"
        assert params["wind_speed_unit"] == "kmh"
        assert params["start_date"] == "2026-10-29"
        assert params["end_date"] == "2026-10-30"
        assert request.extensions["timeout"]["read"] == 3
        return httpx.Response(200, json=_response_payload())

    city = get_city("shanghai")
    assert city is not None
    result = _provider(handler).fetch(city, _query())

    assert result.provider_id == "open-meteo.forecast"
    assert result.days[0].weather_code == 1
    assert result.days[0].temperature_max_c == 21.5
    assert result.days[1].precipitation_probability_max_pct == 80
    assert result.location.requested_latitude == city.center.latitude
    assert result.location.resolved_longitude == 121.5
    assert result.location.elevation_m == 12
    assert "Open-Meteo" in result.source.attribution


def test_null_and_missing_columns_become_missing_fields_or_missing_days() -> None:
    payload = {
        "daily": {
            "time": ["2026-10-29", "2026-10-30"],
            "weather_code": [None],
            "temperature_2m_max": [20.0],
            "temperature_2m_min": [None],
        }
    }
    city = get_city("shanghai")
    assert city is not None
    result = _provider(lambda _: httpx.Response(200, json=payload)).fetch(city, _query())
    assert len(result.days) == 1
    assert result.days[0].temperature_max_c == 20
    assert "weather_code" in result.days[0].missing_fields
    assert result.location.resolved_latitude is None


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, "rate_limited"),
        (401, "policy_unavailable"),
        (403, "policy_unavailable"),
        (503, "503"),
        (400, "unavailable"),
    ],
)
def test_provider_statuses_are_mapped_without_upstream_body(status: int, expected: str) -> None:
    city = get_city("shanghai")
    assert city is not None
    provider = _provider(lambda _: httpx.Response(status, text="sensitive upstream detail"))
    with pytest.raises(WeatherProviderError) as error:
        provider.fetch(city, _query())
    assert error.value.status == expected
    assert "sensitive" not in str(error.value)


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b"\xff\xfe",
        json.dumps({"daily": {"time": ["not-a-date"], "temperature_2m_max": [12]}}).encode(),
    ],
)
def test_malformed_responses_fail_closed(body: bytes) -> None:
    city = get_city("shanghai")
    assert city is not None
    with pytest.raises(WeatherProviderError, match="weather provider unavailable"):
        _provider(lambda _: httpx.Response(200, content=body)).fetch(city, _query())


def test_oversized_response_is_rejected_before_full_body_is_read() -> None:
    city = get_city("shanghai")
    assert city is not None

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * (MAX_RESPONSE_BYTES + 1))

    with pytest.raises(WeatherProviderError) as error:
        _provider(handler).fetch(city, _query())
    assert error.value.status == "unavailable"


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (httpx.ReadTimeout("private details"), "timeout"),
        (httpx.ConnectError("private details"), "connection"),
    ],
)
def test_network_failures_are_sanitized(exception: Exception, expected: str) -> None:
    city = get_city("shanghai")
    assert city is not None
    with pytest.raises(WeatherProviderError) as error:
        _provider(lambda _: (_ for _ in ()).throw(exception)).fetch(city, _query())
    assert error.value.status == expected
    assert "private details" not in str(error.value)
