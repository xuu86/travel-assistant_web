from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.contracts import ErrorCode, EvidenceState, ResultState, SourceRef
from app.modules.assistant.contracts import AssistantEvidence, ChatRequest
from app.modules.assistant.providers.base import AssistantProviderError
from app.modules.assistant.providers.fake import FakeAssistantProvider
from app.modules.assistant.service import AssistantService


class SequenceProvider:
    def __init__(self, outcomes: list[str | AssistantProviderError]) -> None:
        self.outcomes = outcomes
        self.calls: list[list[dict[str, str]]] = []

    async def complete(self, messages: list[dict[str, str]]) -> str:
        self.calls.append([item.copy() for item in messages])
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, AssistantProviderError):
            raise outcome
        return outcome


def configured_settings() -> Settings:
    return Settings(
        _env_file=None,
        model_base_url="https://model.example.com/v1",
        model_api_key="server-key-sentinel",
        model_name="fixture-model",
    )


def run(service: AssistantService, message: str = "请帮我安排轻松一点"):
    return asyncio.run(service.chat(ChatRequest(message=message), request_id=uuid4()))


async def no_sleep(_: float) -> None:
    return None


def test_unconfigured_service_does_not_create_or_call_provider() -> None:
    service = AssistantService(Settings(_env_file=None))

    response = run(service)

    assert response.state is ResultState.UNCONFIGURED
    assert response.reply == ""
    assert response.error is not None
    assert response.error.code is ErrorCode.UNCONFIGURED


def test_service_parses_reply_without_returning_client_evidence_sources() -> None:
    provider = FakeAssistantProvider(
        content=json.dumps(
            {
                "reply": "可以安排两天的轻松行程。",
                "patch": {"pace": "relaxed", "travelers": 2},
                "sources": [{"source_id": "invented.source", "display_name": "伪造来源"}],
            },
            ensure_ascii=False,
        )
    )
    service = AssistantService(configured_settings(), provider=provider)

    response = run(service)

    assert response.state is ResultState.LIVE
    assert response.reply == "可以安排两天的轻松行程。"
    assert response.candidate_patch is not None
    assert response.candidate_patch.pace == "relaxed"
    assert response.sources == []
    assert provider.calls[0][-1] == {"role": "user", "content": "请帮我安排轻松一点"}


def test_service_marks_client_evidence_unverified_and_hides_source_identifiers() -> None:
    provider = FakeAssistantProvider(
        content='{"reply":"可先核实天气，再安排户外活动。","patch":null}'
    )
    service = AssistantService(configured_settings(), provider=provider)
    request = ChatRequest(
        message="根据资料给建议",
        evidence=[AssistantEvidence(
            evidence_id="weather-1",
            kind="weather",
            summary="晴，最高 20°C",
            state="live",
            source=SourceRef(
                source_id="forged.provider",
                display_name="客户端天气资料",
                retrieved_at=datetime(2026, 10, 29, tzinfo=UTC),
                evidence_state=EvidenceState.VERIFIED,
            ),
        )],
    )

    response = asyncio.run(service.chat(request, request_id=uuid4()))
    sent = json.dumps(provider.calls[0], ensure_ascii=False)

    assert response.sources == []
    assert "服务端未核实" in sent
    assert "forged.provider" not in sent
    assert "user_provided" in sent


def test_service_does_not_send_trip_context_or_evidence_by_default() -> None:
    provider = FakeAssistantProvider(content='{"reply":"可以先告诉我预算。","patch":null}')
    service = AssistantService(configured_settings(), provider=provider)
    request = ChatRequest(
        message="有什么建议？",
        trip_context={"destination": "杭州", "budget_fen": 500_000},
    )

    response = asyncio.run(service.chat(request, request_id=uuid4()))
    sent = json.dumps(provider.calls[0], ensure_ascii=False)

    assert response.state is ResultState.LIVE
    assert "杭州" not in sent
    assert "500000" not in sent


def test_service_adds_only_allowlisted_trip_context_when_explicitly_enabled() -> None:
    provider = FakeAssistantProvider(content='{"reply":"收到。","patch":null}')
    service = AssistantService(configured_settings(), provider=provider)
    request = ChatRequest(
        message="按我的条件建议。",
        trip_context={"destination": "杭州", "budget_fen": 500_000},
        include_trip_context=True,
    )

    asyncio.run(service.chat(request, request_id=uuid4()))
    sent = json.dumps(provider.calls[0], ensure_ascii=False)

    assert "杭州" in sent
    assert "500000" in sent
    assert "user_id" not in sent


def test_service_retries_retryable_provider_failures_up_to_five_total_attempts() -> None:
    provider = SequenceProvider([AssistantProviderError("timeout") for _ in range(5)])
    service = AssistantService(configured_settings(), provider=provider, sleep=no_sleep)

    response = run(service)

    assert response.state is ResultState.UNAVAILABLE
    assert len(provider.calls) == 5


@pytest.mark.parametrize(
    "status",
    ["rate_limited", "policy_unavailable", "unavailable"],
)
def test_service_does_not_retry_nonretryable_provider_failures(status: str) -> None:
    provider = SequenceProvider([AssistantProviderError(status)])
    service = AssistantService(configured_settings(), provider=provider, sleep=no_sleep)

    response = run(service)

    assert len(provider.calls) == 1
    assert response.error is not None
    assert response.error.code in {
        ErrorCode.RATE_LIMITED,
        ErrorCode.POLICY_UNAVAILABLE,
        ErrorCode.PROVIDER_UNAVAILABLE,
    }


@pytest.mark.parametrize(
    "content",
    [
        "not-json",
        '{"reply":"","patch":null}',
        '{"reply":"回答","patch":{"locked_reservations":[]}}',
        '{"reply":"回答","patch":{"budget_fen":true}}',
        '{"reply":"回答","patch":null,"extra":"private"}',
    ],
)
def test_service_rejects_invalid_model_output_without_generated_content(content: str) -> None:
    provider = FakeAssistantProvider(content=content)
    service = AssistantService(configured_settings(), provider=provider, sleep=no_sleep)

    response = run(service)

    assert response.state is ResultState.UNAVAILABLE
    assert response.reply == ""
    assert response.candidate_patch is None
    assert response.sources == []
    assert len(provider.calls) == 1
