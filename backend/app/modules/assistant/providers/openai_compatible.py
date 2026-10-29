from __future__ import annotations

import json

import httpx
from pydantic import SecretStr

from app.modules.assistant.providers.base import (
    AssistantProviderError,
    ProviderMessage,
    ProviderStatus,
)

MAX_RESPONSE_BYTES = 128_000
_RESPONSE_STATUS: dict[int, ProviderStatus] = {
    401: "policy_unavailable",
    403: "policy_unavailable",
    429: "rate_limited",
    502: "502",
    503: "503",
    504: "504",
}


class OpenAICompatibleProvider:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: SecretStr | str,
        model_name: str,
        timeout_seconds: float = 30,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key if isinstance(api_key, SecretStr) else SecretStr(api_key)
        self._model_name = model_name
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    async def complete(self, messages: list[ProviderMessage]) -> str:
        payload = {
            "model": self._model_name,
            "temperature": 0.2,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                async with client.stream(
                    "POST",
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key.get_secret_value()}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    if response.status_code >= 400:
                        raise AssistantProviderError(
                            _RESPONSE_STATUS.get(response.status_code, "unavailable")
                        )
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_RESPONSE_BYTES:
                            raise AssistantProviderError("unavailable")
                        chunks.append(chunk)
        except AssistantProviderError:
            raise
        except httpx.TimeoutException as exc:
            raise AssistantProviderError("timeout") from exc
        except httpx.RequestError as exc:
            raise AssistantProviderError("connection") from exc

        try:
            result = json.loads(b"".join(chunks))
            content = result["choices"][0]["message"]["content"]
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as exc:
            raise AssistantProviderError("unavailable") from exc
        if not isinstance(content, str) or not content.strip():
            raise AssistantProviderError("unavailable")
        return content
