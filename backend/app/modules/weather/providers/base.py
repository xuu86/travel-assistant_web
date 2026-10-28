from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.core.cities import CityRecord
from app.modules.weather.contracts import ProviderForecastPayload, WeatherQuery


class WeatherProviderError(RuntimeError):
    def __init__(self, status: str, message: str = "weather provider unavailable") -> None:
        self.status = status
        super().__init__(message)


class WeatherProvider(Protocol):
    provider_id: str

    def fetch(self, city: CityRecord, query: WeatherQuery) -> ProviderForecastPayload: ...


@dataclass(frozen=True)
class WeatherProviderCall:
    city_id: str
    start_date: str
    end_date: str


@dataclass
class FakeWeatherProvider:
    """Explicitly test-only provider. It never performs network I/O."""

    payload: ProviderForecastPayload | None = None
    error: WeatherProviderError | None = None
    provider_id: str = "fixture.weather"
    calls: list[WeatherProviderCall] = field(default_factory=list)

    def fetch(self, city: CityRecord, query: WeatherQuery) -> ProviderForecastPayload:
        self.calls.append(
            WeatherProviderCall(
                city_id=city.id,
                start_date=query.start_date.isoformat(),
                end_date=query.end_date.isoformat(),
            )
        )
        if self.error is not None:
            raise self.error
        if self.payload is None:
            raise WeatherProviderError("unconfigured", "fixture provider has no payload")
        return self.payload


def select_provider(
    provider_id: str | None, *, fake: FakeWeatherProvider | None = None
) -> WeatherProvider | None:
    """Return only explicitly injected test fake; production defaults to no provider."""
    if provider_id in (None, "", "unconfigured"):
        return None
    if provider_id == "fixture.weather":
        return fake if fake is not None else FakeWeatherProvider()
    raise WeatherProviderError("unconfigured", "requested weather provider is not registered")
