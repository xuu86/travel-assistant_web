from __future__ import annotations

from typing import Literal, Protocol

ProviderStatus = Literal[
    "timeout",
    "connection",
    "502",
    "503",
    "504",
    "rate_limited",
    "policy_unavailable",
    "unavailable",
]
ProviderMessage = dict[str, str]
RETRYABLE_PROVIDER_STATUSES = frozenset({"timeout", "connection", "502", "503", "504"})


class AssistantProviderError(RuntimeError):
    """A provider failure with a safe, normalized public status."""

    def __init__(self, status: ProviderStatus) -> None:
        if status not in RETRYABLE_PROVIDER_STATUSES | {
            "rate_limited",
            "policy_unavailable",
            "unavailable",
        }:
            raise ValueError("Unsupported assistant provider status.")
        self.status: ProviderStatus = status
        self.retryable = status in RETRYABLE_PROVIDER_STATUSES
        super().__init__(status)


class AssistantProvider(Protocol):
    async def complete(self, messages: list[ProviderMessage]) -> str: ...
