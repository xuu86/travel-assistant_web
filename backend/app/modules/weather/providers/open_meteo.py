from __future__ import annotations

import json
from datetime import UTC, date, datetime
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.cities import CityRecord
from app.core.contracts import EvidenceState, ResultState, SourceRef
from app.modules.weather.contracts import (
    ProviderForecastPayload,
    WeatherDay,
    WeatherLocationMetadata,
    WeatherQuery,
)
from app.modules.weather.providers.base import WeatherProviderError

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
MAX_RESPONSE_BYTES = 256 * 1024
DAILY_VARIABLES = (
    "weather_code",
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_probability_max",
    "precipitation_sum",
    "wind_speed_10m_max",
)


class OpenMeteoWeatherProvider:
    provider_id = "open-meteo.forecast"

    def __init__(self, *, timeout_seconds: float = 8.0, client: httpx.Client | None = None) -> None:
        self.timeout_seconds = timeout_seconds
        self._client = client

    def fetch(self, city: CityRecord, query: WeatherQuery) -> ProviderForecastPayload:
        params = {
            "latitude": str(city.center.latitude),
            "longitude": str(city.center.longitude),
            "daily": ",".join(DAILY_VARIABLES),
            "timezone": "Asia/Shanghai",
            "temperature_unit": "celsius",
            "precipitation_unit": "mm",
            "wind_speed_unit": "kmh",
            "start_date": query.start_date.isoformat(),
            "end_date": query.end_date.isoformat(),
        }
        try:
            if self._client is None:
                with httpx.Client(timeout=self.timeout_seconds, follow_redirects=False) as client:
                    response_body, status_code = self._request(
                        client, params, self.timeout_seconds
                    )
            else:
                response_body, status_code = self._request(
                    self._client, params, self.timeout_seconds
                )
        except httpx.TimeoutException as exc:
            raise WeatherProviderError("timeout") from exc
        except httpx.RequestError as exc:
            raise WeatherProviderError("connection") from exc

        if status_code == 429:
            raise WeatherProviderError("rate_limited")
        if status_code in (401, 403):
            raise WeatherProviderError("policy_unavailable")
        if status_code >= 500:
            raise WeatherProviderError(str(status_code))
        if status_code < 200 or status_code >= 300:
            raise WeatherProviderError("unavailable")

        try:
            data = json.loads(response_body)
            return self._map_response(city, data)
        except (
            json.JSONDecodeError,
            UnicodeDecodeError,
            TypeError,
            ValueError,
            KeyError,
            OverflowError,
            ValidationError,
        ) as exc:
            raise WeatherProviderError("unavailable") from exc

    @staticmethod
    def _request(
        client: httpx.Client,
        params: dict[str, str],
        timeout_seconds: float,
    ) -> tuple[bytes, int]:
        with client.stream(
            "GET", FORECAST_URL, params=params, timeout=timeout_seconds, follow_redirects=False
        ) as response:
            if response.status_code < 200 or response.status_code >= 300:
                return b"", response.status_code
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > MAX_RESPONSE_BYTES:
                    raise WeatherProviderError("unavailable")
                chunks.append(chunk)
            return b"".join(chunks), response.status_code

    @classmethod
    def _map_response(cls, city: CityRecord, data: Any) -> ProviderForecastPayload:
        if not isinstance(data, dict):
            raise TypeError("invalid response")
        if "timezone" in data and data["timezone"] != "Asia/Shanghai":
            raise ValueError("unexpected forecast timezone")
        expected_units = {
            "temperature_2m_max": "°C",
            "temperature_2m_min": "°C",
            "precipitation_probability_max": "%",
            "precipitation_sum": "mm",
            "wind_speed_10m_max": "km/h",
        }
        if "daily_units" in data:
            units = data["daily_units"]
            if not isinstance(units, dict) or any(
                name in units and units[name] != unit for name, unit in expected_units.items()
            ):
                raise ValueError("unexpected forecast units")
        daily = data.get("daily")
        if not isinstance(daily, dict) or not isinstance(daily.get("time"), list):
            raise ValueError("missing daily forecast")
        dates = daily["time"]
        columns = {name: daily.get(name) for name in DAILY_VARIABLES}
        retrieved_at = datetime.now(UTC)
        resolved_latitude = _optional_float(data.get("latitude"))
        resolved_longitude = _optional_float(data.get("longitude"))
        elevation = _optional_float(data.get("elevation"))
        location = WeatherLocationMetadata(
            city_id=city.id,
            requested_latitude=city.center.latitude,
            requested_longitude=city.center.longitude,
            resolved_latitude=resolved_latitude,
            resolved_longitude=resolved_longitude,
            elevation_m=elevation,
        )
        days: list[WeatherDay] = []
        field_map = {
            "weather_code": "weather_code",
            "temperature_max_c": "temperature_2m_max",
            "temperature_min_c": "temperature_2m_min",
            "precipitation_probability_max_pct": "precipitation_probability_max",
            "precipitation_sum_mm": "precipitation_sum",
            "wind_speed_10m_max_kmh": "wind_speed_10m_max",
        }
        for index, raw_date in enumerate(dates):
            if not isinstance(raw_date, str):
                raise ValueError("invalid forecast date")
            values = {
                target: _value_at(columns[source], index) for target, source in field_map.items()
            }
            if all(value is None for value in values.values()):
                continue
            days.append(WeatherDay(date=date.fromisoformat(raw_date), **values))
        if not days:
            raise ValueError("forecast has no usable days")
        return ProviderForecastPayload(
            provider_id=cls.provider_id,
            state=ResultState.LIVE,
            retrieved_at=retrieved_at,
            source=SourceRef(
                source_id=cls.provider_id,
                display_name="Open-Meteo Forecast API",
                url="https://open-meteo.com/en/docs",
                retrieved_at=retrieved_at,
                attribution=(
                    "Weather data by Open-Meteo.com, licensed under CC BY 4.0. "
                    "Daily fields selected and renamed."
                ),
                evidence_state=EvidenceState.UNKNOWN,
            ),
            location=location,
            days=days,
        )


def _value_at(column: Any, index: int) -> Any:
    if column is None:
        return None
    if not isinstance(column, list):
        raise ValueError("invalid daily column")
    if index >= len(column):
        return None
    return column[index]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
