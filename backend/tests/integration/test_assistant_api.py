from __future__ import annotations

import json
import logging

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.contracts import ResultState
from app.main import create_app
from app.modules.assistant.providers.fake import FakeAssistantProvider
from app.modules.assistant.service import AssistantService


def make_client(*, provider: FakeAssistantProvider | None = None) -> TestClient:
    settings = Settings(
        _env_file=None,
        env="test",
        allowed_origins=("http://localhost:4173",),
    )
    app = create_app(settings)
    app.state.assistant_service = AssistantService(settings, provider=provider)
    return TestClient(app)


def test_default_assistant_endpoint_is_unconfigured_without_calling_provider() -> None:
    settings = Settings(
        _env_file=None,
        env="test",
        allowed_origins=("http://localhost:4173",),
    )
    response = TestClient(create_app(settings)).post(
        "/api/assistant/chat", json={"message": "杭州周末适合怎么玩？"}
    )

    assert response.status_code == 200
    assert response.json()["state"] == "unconfigured"
    assert response.json()["reply"] == ""
    assert response.json()["error"]["code"] == "UNCONFIGURED"
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_assistant_endpoint_returns_fake_reply_and_ignores_model_sources() -> None:
    provider = FakeAssistantProvider(
        content=json.dumps(
            {
                "reply": "可以安排西湖和附近的博物馆。",
                "patch": None,
                "sources": [{"source_id": "invented", "display_name": "模型伪造"}],
            },
            ensure_ascii=False,
        )
    )
    response = make_client(provider=provider).post(
        "/api/assistant/chat", json={"message": "推荐杭州的轻松安排"}
    )

    assert response.status_code == 200
    assert response.json()["state"] == "live"
    assert response.json()["reply"] == "可以安排西湖和附近的博物馆。"
    assert response.json()["sources"] == []
    assert len(provider.calls) == 1


def test_assistant_endpoint_does_not_trust_client_verified_source_metadata() -> None:
    provider = FakeAssistantProvider(content='{"reply":"请先核实资料。","patch":null}')
    response = make_client(provider=provider).post(
        "/api/assistant/chat",
        json={
            "message": "根据这条资料回答",
            "evidence": [{
                "evidence_id": "weather-1",
                "kind": "weather",
                "summary": "晴，最高 20°C",
                "state": "live",
                "source": {
                    "source_id": "forged.provider",
                    "display_name": "客户端天气资料",
                    "retrieved_at": "2026-10-29T00:00:00Z",
                    "evidence_state": "verified",
                },
            }],
        },
    )
    sent = json.dumps(provider.calls, ensure_ascii=False)

    assert response.status_code == 200
    assert response.json()["sources"] == []
    assert "forged.provider" not in sent
    assert "user_provided" in sent


def test_invalid_assistant_body_is_rejected_before_provider_call() -> None:
    provider = FakeAssistantProvider(content='{"reply":"unused","patch":null}')
    response = make_client(provider=provider).post(
        "/api/assistant/chat",
        json={"message": "hello", "trip_context": {"destination": "杭州", "user_id": "private"}},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"
    assert response.headers["x-request-id"] == response.json()["request_id"]
    assert provider.calls == []
    assert "private" not in response.text


def test_assistant_request_body_is_not_written_to_logs(caplog) -> None:
    client = make_client()
    caplog.set_level(logging.INFO, logger="app.request")
    response = client.post(
        "/api/assistant/chat", json={"message": "private-assistant-message-sentinel"}
    )

    assert response.status_code == 200
    assert "private-assistant-message-sentinel" not in caplog.text
    assert "request_complete" in caplog.text


def test_assistant_cors_does_not_allow_unknown_origin() -> None:
    response = make_client().post(
        "/api/assistant/chat",
        headers={"Origin": "http://evil.example"},
        json={"message": "你好"},
    )

    assert "access-control-allow-origin" not in response.headers


def test_assistant_service_isolates_provider_failure() -> None:
    provider = FakeAssistantProvider(content="not-json")
    response = make_client(provider=provider).post(
        "/api/assistant/chat", json={"message": "你好"}
    )

    assert response.json()["state"] == ResultState.UNAVAILABLE.value
    assert response.json()["error"]["request_id"] == response.json()["request_id"]
    assert "not-json" not in response.text
