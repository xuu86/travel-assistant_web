from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.core.cities import CityRecord
from app.modules.weather.contracts import ProviderForecastPayload, WeatherQuery
from app.modules.weather.providers.base import WeatherProvider, WeatherProviderError

MAX_RETRIES = 1
REQUEST_TIMEOUT_SECONDS = 8.0
CACHE_TTL = timedelta(minutes=15)
_TRANSIENT_STATUSES = {"timeout", "connection", "502", "503", "504"}


@dataclass(frozen=True)
class WeatherCacheKey:
    provider_id: str
    city_id: str
    start_date: str
    end_date: str


@dataclass(frozen=True)
class WeatherCacheEntry:
    payload: ProviderForecastPayload
    expires_at: datetime


class WeatherRuntime:
    """Bounded retry and process-local cache around an injected provider."""

    def __init__(
        self,
        provider: WeatherProvider,
        *,
        now: Callable[[], datetime] | None = None,
        timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
        cache_ttl: timedelta = CACHE_TTL,
    ) -> None:
        self.provider = provider
        self.now = now or (lambda: datetime.now(UTC))
        self.timeout_seconds = timeout_seconds
        self.cache_ttl = cache_ttl
        self._cache: dict[WeatherCacheKey, WeatherCacheEntry] = {}

    def fetch(self, city: CityRecord, query: WeatherQuery) -> ProviderForecastPayload:
        key = WeatherCacheKey(
            provider_id=self.provider.provider_id,
            city_id=city.id,
            start_date=query.start_date.isoformat(),
            end_date=query.end_date.isoformat(),
        )
        cached = self._cache.get(key)
        current = self.now()
        if cached is not None:
            if current < cached.expires_at:
                return cached.payload
            del self._cache[key]

        payload = self._fetch_with_bounded_retry(city, query)
        if payload.state.value == "live":
            self._cache[key] = WeatherCacheEntry(
                payload=payload,
                expires_at=current + self.cache_ttl,
            )
        return payload

    def _fetch_with_bounded_retry(
        self,
        city: CityRecord,
        query: WeatherQuery,
    ) -> ProviderForecastPayload:
        attempts = 0
        while True:
            try:
                return self.provider.fetch(city, query)
            except WeatherProviderError as exc:
                if exc.status not in _TRANSIENT_STATUSES or attempts >= MAX_RETRIES:
                    raise
                attempts += 1
