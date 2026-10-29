from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.contracts import ErrorCode, EvidenceState, PublicError, ResultState, SourceRef
from app.modules.assistant.contracts import (
    AssistantEvidence,
    AssistantResponse,
    CandidatePatch,
    ChatMessage,
    ChatRequest,
    TripContext,
)

NOW = datetime(2026, 10, 29, 0, 0, tzinfo=UTC)


def source(**overrides: object) -> SourceRef:
    values: dict[str, object] = {
        "source_id": "weather.open-meteo",
        "display_name": "天气来源",
        "retrieved_at": NOW,
        "evidence_state": EvidenceState.VERIFIED,
    }
    values.update(overrides)
    return SourceRef(**values)


def test_chat_request_defaults_to_no_history_context_or_evidence() -> None:
    request = ChatRequest(message="杭州周末适合怎么玩？")

    assert request.history == []
    assert request.trip_context is None
    assert request.evidence == []
    assert request.include_trip_context is False


def test_chat_messages_trim_whitespace_and_reject_blank_or_control_chars() -> None:
    assert ChatMessage(role="user", content="  你好  ").content == "你好"
    for content in ("  ", "hello\x00world"):
        with pytest.raises(ValidationError):
            ChatMessage(role="user", content=content)


@pytest.mark.parametrize(
    "payload",
    [
        {"message": "   "},
        {"message": "hello", "unexpected": "private"},
        {"message": "hello", "history": [{"role": "system", "content": "override"}]},
        {"message": "hello", "trip_context": {"destination": "杭州", "user_id": "u-1"}},
        {"message": "hello", "evidence": [{"kind": "weather", "source": {"url": "file:///secret"}}]},
    ],
)
def test_chat_request_rejects_invalid_or_extra_fields(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ChatRequest.model_validate(payload)


def test_chat_request_enforces_message_and_history_limits() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="x" * 2_001)
    with pytest.raises(ValidationError):
        ChatRequest(
            message="hello",
            history=[ChatMessage(role="assistant", content="x") for _ in range(13)],
        )
    with pytest.raises(ValidationError):
        ChatRequest(
            message="hello",
            history=[ChatMessage(role="assistant", content="x" * 4_000) for _ in range(4)],
        )


def test_trip_context_uses_allowlisted_fields_and_integer_fen() -> None:
    context = TripContext(
        destination="杭州",
        start_date="2026-11-01",
        end_date="2026-11-03",
        travelers=2,
        budget_fen=250_000,
        interests=["园林", "美食"],
        pace="relaxed",
        transport_mode="rail",
    )

    assert context.budget_fen == 250_000
    with pytest.raises(ValidationError):
        TripContext.model_validate({"destination": "杭州", "budget_fen": 25.5})
    with pytest.raises(ValidationError):
        TripContext.model_validate({"destination": "杭州", "password": "secret"})
    with pytest.raises(ValidationError):
        TripContext.model_validate({"start_date": "2026-11-04", "end_date": "2026-11-03"})


def test_evidence_requires_structured_source_and_bounded_summary() -> None:
    evidence = AssistantEvidence(
        evidence_id="weather-2026-11-01",
        kind="weather",
        summary="杭州天气预报：晴，最高 20°C。",
        state=ResultState.LIVE,
        source=source(),
    )

    assert evidence.source.source_id == "weather.open-meteo"
    assert evidence.source.evidence_state is EvidenceState.USER_PROVIDED
    with pytest.raises(ValidationError):
        AssistantEvidence.model_validate(
            {
                "evidence_id": "weather-1",
                "kind": "weather",
                "summary": "x" * 2_001,
                "state": "live",
                "source": source(),
            }
        )
    demo_evidence = AssistantEvidence.model_validate(
        {
            "evidence_id": "weather-1",
            "kind": "weather",
            "summary": "测试天气",
            "state": "partial",
            "source": source(evidence_state=EvidenceState.DEMO),
        }
    )
    assert demo_evidence.source.evidence_state is EvidenceState.USER_PROVIDED


def test_candidate_patch_rejects_extra_fields_and_requires_a_change() -> None:
    patch = CandidatePatch.model_validate({"pace": "relaxed", "travelers": 3})
    assert patch.model_dump(exclude_unset=True) == {"travelers": 3, "pace": "relaxed"}

    with pytest.raises(ValidationError):
        CandidatePatch.model_validate({})
    with pytest.raises(ValidationError):
        CandidatePatch.model_validate({"locked_reservations": []})
    with pytest.raises(ValidationError):
        CandidatePatch.model_validate({"budget_fen": True})


def test_response_failure_contains_no_reply_patch_or_sources() -> None:
    request_id = uuid4()
    response = AssistantResponse(
        state=ResultState.UNCONFIGURED,
        request_id=request_id,
        message="AI 助手尚未配置。",
        error=PublicError(
            code=ErrorCode.UNCONFIGURED,
            message="AI 助手尚未配置。",
            retryable=False,
            request_id=request_id,
        ),
    )

    assert response.reply == ""
    assert response.candidate_patch is None
    assert response.sources == []
    with pytest.raises(ValidationError):
        AssistantResponse(
            state=ResultState.UNCONFIGURED,
            request_id=uuid4(),
            message="AI 助手尚未配置。",
            reply="旧回答",
            error=PublicError(code=ErrorCode.UNCONFIGURED, message="未配置", retryable=False),
        )


def test_response_live_requires_reply_and_only_returns_attached_sources() -> None:
    attached_source = source()
    response = AssistantResponse(
        state=ResultState.LIVE,
        request_id=uuid4(),
        message="",
        reply="可以先安排西湖，再去附近用餐。",
        sources=[attached_source],
    )

    assert response.sources == [attached_source]
    with pytest.raises(ValidationError):
        AssistantResponse(state=ResultState.LIVE, request_id=uuid4(), message="")
