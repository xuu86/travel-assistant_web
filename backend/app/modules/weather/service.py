from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from app.core.cities import get_city
from app.core.contracts import Coverage, DateRange, ErrorCode, PublicError, ResultState
from app.core.errors import ServiceError
from app.modules.weather.contracts import (
    WeatherLocationMetadata,
    WeatherQuery,
    WeatherResult,
)
from app.modules.weather.providers.base import WeatherProvider, WeatherProviderError

_PROVIDER_ERROR_MAP: dict[str, tuple[ResultState, ErrorCode, str]] = {
    "unconfigured": (ResultState.UNCONFIGURED, ErrorCode.UNCONFIGURED, "天气服务尚未配置。"),
    "rate_limited": (
        ResultState.RATE_LIMITED,
        ErrorCode.RATE_LIMITED,
        "天气查询暂受额度限制，请稍后重试。",
    ),
    "policy_unavailable": (
        ResultState.POLICY_UNAVAILABLE,
        ErrorCode.POLICY_UNAVAILABLE,
        "天气服务权限或政策暂不可用。",
    ),
    "unavailable": (ResultState.UNAVAILABLE, ErrorCode.PROVIDER_UNAVAILABLE, "天气服务暂不可用。"),
}


def _date_ranges(dates: list[date]) -> list[tuple[date, date]]:
    if not dates:
        return []
    sorted_dates = sorted(set(dates))
    ranges: list[tuple[date, date]] = []
    start = previous = sorted_dates[0]
    for current in sorted_dates[1:]:
        if current != previous + timedelta(days=1):
            ranges.append((start, previous))
            start = current
        previous = current
    ranges.append((start, previous))
    return ranges


class WeatherService:
    def __init__(self, provider: WeatherProvider | None, *, today: Callable[[], date]) -> None:
        self.provider = provider
        self.today = today

    def forecast(self, query: WeatherQuery, *, request_id: UUID) -> WeatherResult:
        city = get_city(query.city_id)
        if city is None:
            raise ServiceError(ErrorCode.VALIDATION_ERROR, retryable=False)
        location = WeatherLocationMetadata(
            city_id=city.id,
            requested_latitude=city.center.latitude,
            requested_longitude=city.center.longitude,
        )
        if self.provider is None:
            return self._empty_result(
                state=ResultState.UNCONFIGURED,
                error_code=ErrorCode.UNCONFIGURED,
                message="天气服务尚未配置。",
                location=location,
                request_id=request_id,
            )

        current_day = self.today()
        provider_start = max(query.start_date, current_day)
        if provider_start > query.end_date:
            return self._no_coverage_result(query, location, request_id)

        provider_query = WeatherQuery(
            city_id=query.city_id,
            start_date=provider_start,
            end_date=query.end_date,
        )
        try:
            payload = self.provider.fetch(city, provider_query)
        except WeatherProviderError as exc:
            state, error_code, message = _PROVIDER_ERROR_MAP.get(
                exc.status,
                (ResultState.UNAVAILABLE, ErrorCode.PROVIDER_UNAVAILABLE, "天气服务暂不可用。"),
            )
            return self._empty_result(
                state=state,
                error_code=error_code,
                message=message,
                location=location,
                request_id=request_id,
            )

        valid_days = {
            day.date: day for day in payload.days if provider_start <= day.date <= query.end_date
        }
        covered_dates = sorted(valid_days)
        missing_dates = [
            current
            for offset in range(query.days)
            if (current := query.start_date + timedelta(days=offset)) not in valid_days
        ]
        coverage = Coverage(
            requested=DateRange(start=query.start_date, end=query.end_date),
            covered=_as_coverage_ranges(covered_dates),
            missing=_as_coverage_ranges(missing_dates),
        )
        resolved_location = payload.location
        if not covered_dates:
            return WeatherResult(
                state=ResultState.NO_COVERAGE,
                items=[],
                sources=[],
                queried_at=payload.retrieved_at,
                request_id=request_id,
                message="请求日期暂无可用天气预报。",
                coverage=coverage,
                error=None,
                location=resolved_location,
            )
        state = (
            payload.state
            if payload.state is ResultState.DEMO
            else (ResultState.LIVE if not missing_dates else ResultState.PARTIAL)
        )
        return WeatherResult(
            state=state,
            items=[valid_days[day] for day in covered_dates],
            sources=[payload.source],
            queried_at=payload.retrieved_at,
            request_id=request_id,
            message="天气数据来自测试 fixture。" if state is ResultState.DEMO else "",
            coverage=coverage,
            error=None,
            location=resolved_location,
        )

    @staticmethod
    def _empty_result(
        *,
        state: ResultState,
        error_code: ErrorCode,
        message: str,
        location: WeatherLocationMetadata,
        request_id: UUID,
    ) -> WeatherResult:
        return WeatherResult(
            state=state,
            items=[],
            sources=[],
            queried_at=datetime.now(UTC),
            request_id=request_id,
            message=message,
            coverage=None,
            error=PublicError(
                code=error_code,
                message=message,
                retryable=error_code in {ErrorCode.RATE_LIMITED, ErrorCode.PROVIDER_UNAVAILABLE},
                request_id=request_id,
            ),
            location=location,
        )

    @staticmethod
    def _no_coverage_result(
        query: WeatherQuery,
        location: WeatherLocationMetadata,
        request_id: UUID,
    ) -> WeatherResult:
        coverage = Coverage(
            requested=DateRange(start=query.start_date, end=query.end_date),
            covered=[],
            missing=[DateRange(start=query.start_date, end=query.end_date)],
        )
        return WeatherResult(
            state=ResultState.NO_COVERAGE,
            items=[],
            sources=[],
            queried_at=datetime.now(UTC),
            request_id=request_id,
            message="请求日期暂无可用天气预报。",
            coverage=coverage,
            error=None,
            location=location,
        )


def _as_coverage_ranges(dates: list[date]) -> list[DateRange]:
    return [{"start": start, "end": end} for start, end in _date_ranges(dates)]



