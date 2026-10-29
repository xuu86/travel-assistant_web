from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.modules.assistant.providers.base import AssistantProviderError
from app.modules.assistant.providers.fake import FakeAssistantProvider
from app.modules.assistant.providers.openai_compatible import OpenAICompatibleProvider


@pytest.mark.parametrize(
    "status",
    ["rate_limited", "policy_unavailable", "unavailable"],
)
def test_fake_provider_records_calls_and_injects_curated_failures(status: str) -> None:
    provider = FakeAssistantProvider(error=AssistantProviderError(status))

    with pytest.raises(AssistantProviderError) as exc_info:
        asyncio.run(provider.complete([{"role": "user", "content": "private-message"}]))

    assert exc_info.value.status == status
    assert provider.calls == [[{"role": "user", "content": "private-message"}]]
    assert "private-message" not in str(exc_info.value)


def test_fake_provider_returns_configured_content_without_network() -> None:
    provider = FakeAssistantProvider(content='{"reply":"你好","patch":{}}')

    response = asyncio.run(provider.complete([{"role": "user", "content": "你好"}]))

    assert response == '{"reply":"你好","patch":{}}'
    assert len(provider.calls) == 1


def test_fake_provider_without_content_or_error_fails_safely() -> None:
    provider = FakeAssistantProvider()

    with pytest.raises(AssistantProviderError) as exc_info:
        asyncio.run(provider.complete([]))

    assert exc_info.value.status == "unavailable"
    assert provider.calls == [[]]


def test_provider_error_rejects_unknown_status() -> None:
    with pytest.raises(ValueError):
        AssistantProviderError("secret-provider-error")


def test_http_provider_sends_server_key_model_and_messages() -> None:
    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"reply":"你好","patch":{}}'}}]},
        )

    provider = OpenAICompatibleProvider(
        base_url="https://model.example.com/v1",
        api_key="server-secret",
        model_name="fixture-model",
        transport=httpx.MockTransport(handler),
    )
    result = asyncio.run(provider.complete([{"role": "user", "content": "你好"}]))

    assert result == '{"reply":"你好","patch":{}}'
    assert captured["url"] == "https://model.example.com/v1/chat/completions"
    assert captured["authorization"] == "Bearer server-secret"
    assert captured["payload"] == {
        "model": "fixture-model",
        "temperature": 0.2,
        "messages": [{"role": "user", "content": "你好"}],
        "response_format": {"type": "json_object"},
    }
    assert "server-secret" not in repr(provider)


@pytest.mark.parametrize(
    ("status_code", "expected_status"),
    [(401, "policy_unavailable"), (403, "policy_unavailable"), (429, "rate_limited"), (502, "502")],
)
def test_http_provider_maps_status_without_exposing_response_body(
    status_code: int, expected_status: str
) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, text="provider-private-sentinel")

    provider = OpenAICompatibleProvider(
        base_url="https://model.example.com/v1",
        api_key="server-secret",
        model_name="fixture-model",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AssistantProviderError) as exc_info:
        asyncio.run(provider.complete([]))

    assert exc_info.value.status == expected_status
    assert "provider-private-sentinel" not in str(exc_info.value)
    assert "server-secret" not in str(exc_info.value)


def test_http_provider_rejects_oversized_response() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "x" * 128_001}}]},
        )

    provider = OpenAICompatibleProvider(
        base_url="https://model.example.com/v1",
        api_key="server-secret",
        model_name="fixture-model",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(AssistantProviderError) as exc_info:
        asyncio.run(provider.complete([]))

    assert exc_info.value.status == "unavailable"
