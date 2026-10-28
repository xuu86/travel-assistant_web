from __future__ import annotations

from typing import Literal, Protocol, cast
from uuid import UUID

from app.modules.transport.contracts import FareQuery, FareResult, RouteQuery, RouteResult

ProviderErrorStatus = Literal[
    "unconfigured",
    "no_coverage",
    "rate_limited",
    "policy_unavailable",
    "unavailable",
]
_PROVIDER_ERROR_STATUSES = frozenset(
    {"unconfigured", "no_coverage", "rate_limited", "policy_unavailable", "unavailable"}
)


class TransportProviderError(RuntimeError):
    """Safe provider status without retaining untrusted response text."""

    def __init__(
        self, status: ProviderErrorStatus | str, _private_message: str | None = None
    ) -> None:
        if status not in _PROVIDER_ERROR_STATUSES:
            raise ValueError("Unsupported transport provider status.")
        self.status = cast(ProviderErrorStatus, status)
        super().__init__("transport provider request failed")


class FareProvider(Protocol):
    def search_fares(self, query: FareQuery, *, request_id: UUID) -> FareResult: ...


class RouteProvider(Protocol):
    def search_route(self, query: RouteQuery, *, request_id: UUID) -> RouteResult: ...
