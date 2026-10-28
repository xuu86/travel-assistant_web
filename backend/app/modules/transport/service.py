from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID

from app.core.contracts import ErrorCode, PublicError, ResultState
from app.modules.transport.contracts import (
    FareQuery,
    FareResult,
    RouteQuery,
    RouteResult,
)
from app.modules.transport.providers.base import (
    FareProvider,
    RouteProvider,
    TransportProviderError,
)

_PROVIDER_FAILURES: dict[str, tuple[ResultState, ErrorCode, str, bool]] = {
    "unconfigured": (
        ResultState.UNCONFIGURED,
        ErrorCode.UNCONFIGURED,
        "交通查询尚未配置，不代表没有班次或路线。",
        False,
    ),
    "no_coverage": (
        ResultState.NO_COVERAGE,
        ErrorCode.NO_COVERAGE,
        "当前来源未覆盖此查询条件，不代表没有班次或路线。",
        False,
    ),
    "rate_limited": (
        ResultState.RATE_LIMITED,
        ErrorCode.RATE_LIMITED,
        "交通查询暂受额度限制，请稍后重试。",
        True,
    ),
    "policy_unavailable": (
        ResultState.POLICY_UNAVAILABLE,
        ErrorCode.POLICY_UNAVAILABLE,
        "交通服务权限或政策暂不可用。",
        False,
    ),
    "unavailable": (
        ResultState.UNAVAILABLE,
        ErrorCode.PROVIDER_UNAVAILABLE,
        "交通服务暂不可用，请稍后重试。",
        True,
    ),
}
_STATE_ERRORS: dict[ResultState, tuple[ErrorCode, str, bool]] = {
    state: (code, message, retryable)
    for state, code, message, retryable in _PROVIDER_FAILURES.values()
}
_RESULT_MESSAGES: dict[ResultState, str] = {
    ResultState.LIVE: "本次查询返回结果；班次、价格、余量或路线信息可能变化。",
    ResultState.PARTIAL: "本次查询包含待核实字段；未返回的信息不会自动补齐。",
    ResultState.EMPTY: "本次查询未返回结果；这不表示一定不存在班次或路线。",
    ResultState.DEMO: "当前为测试 fixture 结果，不代表实时班次、票价或路线。",
}
_T = TypeVar("_T", FareResult, RouteResult)


class TransportService:
    """Normalize transport provider results without caching or network fallback."""

    def __init__(
        self,
        fare_provider: FareProvider | None = None,
        route_provider: RouteProvider | None = None,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.fare_provider = fare_provider
        self.route_provider = route_provider
        self.now = now or (lambda: datetime.now(UTC))

    def search_fares(self, query: FareQuery, *, request_id: UUID) -> FareResult:
        if self.fare_provider is None:
            return self._failure_result(
                FareResult, status="unconfigured", request_id=request_id
            )
        try:
            provider_result = self.fare_provider.search_fares(query, request_id=request_id)
            if not isinstance(provider_result, FareResult):
                raise ValueError("Invalid fare provider result type.")
            self._validate_fare_query_match(provider_result, query)
            return self._normalize_result(provider_result, request_id=request_id)
        except TransportProviderError as exc:
            return self._failure_result(
                FareResult, status=exc.status, request_id=request_id
            )
        except Exception:
            return self._failure_result(
                FareResult, status="unavailable", request_id=request_id
            )

    def search_route(self, query: RouteQuery, *, request_id: UUID) -> RouteResult:
        if self.route_provider is None:
            return self._failure_result(
                RouteResult, status="unconfigured", request_id=request_id
            )
        try:
            provider_result = self.route_provider.search_route(query, request_id=request_id)
            if not isinstance(provider_result, RouteResult):
                raise ValueError("Invalid route provider result type.")
            self._validate_route_query_match(provider_result, query)
            return self._normalize_result(provider_result, request_id=request_id)
        except TransportProviderError as exc:
            return self._failure_result(
                RouteResult, status=exc.status, request_id=request_id
            )
        except Exception:
            return self._failure_result(
                RouteResult, status="unavailable", request_id=request_id
            )

    @staticmethod
    def _validate_fare_query_match(result: FareResult, query: FareQuery) -> None:
        for offer in result.items:
            if offer.mode != query.mode or offer.travel_date != query.travel_date:
                raise ValueError("Fare result does not match the requested mode and travel date.")
            if offer.passenger_count is not None and offer.passenger_count != query.passenger_count:
                raise ValueError("Fare result passenger count does not match the query.")
            if (
                offer.price_basis == "party_total"
                and offer.passenger_count != query.passenger_count
            ):
                raise ValueError("Party total does not match the requested passenger count.")

    @staticmethod
    def _validate_route_query_match(result: RouteResult, query: RouteQuery) -> None:
        for route in result.items:
            if route.mode != query.mode:
                raise ValueError("Route result mode does not match the requested mode.")
            if query.depart_at is None and route.duration_basis == "realtime":
                raise ValueError("Realtime route duration requires an explicit departure time.")

    def _normalize_result(self, result: _T, *, request_id: UUID) -> _T:
        payload = result.model_dump(mode="python")
        payload["request_id"] = request_id
        if result.state in _STATE_ERRORS:
            error_code, message, retryable = _STATE_ERRORS[result.state]
            payload["error"] = PublicError(
                code=error_code,
                message=message,
                retryable=retryable,
                request_id=request_id,
            )
            payload["message"] = message
        else:
            if result.error is not None:
                raise ValueError("Successful transport result must not contain a public error.")
            payload["error"] = None
            payload["message"] = _RESULT_MESSAGES[result.state]
        return type(result).model_validate(payload)

    def _failure_result(
        self,
        result_type: type[_T],
        *,
        status: str,
        request_id: UUID,
    ) -> _T:
        state, error_code, message, retryable = _PROVIDER_FAILURES.get(
            status, _PROVIDER_FAILURES["unavailable"]
        )
        return result_type(
            state=state,
            items=[],
            sources=[],
            queried_at=self.now(),
            request_id=request_id,
            message=message,
            error=PublicError(
                code=error_code,
                message=message,
                retryable=retryable,
                request_id=request_id,
            ),
        )
