from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.assistant.providers.base import (
    AssistantProviderError,
    ProviderMessage,
)


@dataclass
class FakeAssistantProvider:
    """Explicitly injected offline provider for tests; never performs network I/O."""

    content: str | None = None
    error: AssistantProviderError | None = None
    calls: list[list[ProviderMessage]] = field(default_factory=list)

    async def complete(self, messages: list[ProviderMessage]) -> str:
        self.calls.append([message.copy() for message in messages])
        if self.error is not None:
            raise self.error
        if self.content is None:
            raise AssistantProviderError("unavailable")
        return self.content
