from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.modules.transport.contracts import FareQuery, FareResult, RouteQuery, RouteResult
from app.modules.transport.providers.base import TransportProviderError


@dataclass(frozen=True, slots=True)
class FareProviderCall:
    query: FareQuery
    request_id: UUID


@dataclass(frozen=True, slots=True)
class RouteProviderCall:
    query: RouteQuery
    request_id: UUID


@dataclass
class FakeFareProvider:
    """Test-only fare provider; never performs network I/O or fabricates fallback data."""

    result: FareResult | None = None
    error: TransportProviderError | None = None
    calls: list[FareProviderCall] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.result is not None and self.error is not None:
            raise ValueError("Configure either a fake result or a fake error, not both.")

    def search_fares(self, query: FareQuery, *, request_id: UUID) -> FareResult:
        self.calls.append(FareProviderCall(query=query, request_id=request_id))
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise TransportProviderError("unconfigured")
        return self.result


@dataclass
class FakeRouteProvider:
    """Test-only route provider; never performs network I/O or fabricates fallback data."""

    result: RouteResult | None = None
    error: TransportProviderError | None = None
    calls: list[RouteProviderCall] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.result is not None and self.error is not None:
            raise ValueError("Configure either a fake result or a fake error, not both.")

    def search_route(self, query: RouteQuery, *, request_id: UUID) -> RouteResult:
        self.calls.append(RouteProviderCall(query=query, request_id=request_id))
        if self.error is not None:
            raise self.error
        if self.result is None:
            raise TransportProviderError("unconfigured")
        return self.result
