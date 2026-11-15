from __future__ import annotations

import json

import pytest

from app.core.config import Settings
from app.core.contracts import ErrorCode
from app.core.errors import ServiceError
from app.modules.auth.credentials import hash_password
from app.modules.auth.service import SESSION_TTL_SECONDS, AuthService


@pytest.fixture
def auth_service() -> AuthService:
    accounts = [
        {
            "username": f"traveler{i}",
            "owner_id": f"user-{i}",
            "display_name": f"旅行用户{i}",
            "password_hash": hash_password("correct-password"),
        }
        for i in range(1, 6)
    ]
    settings = Settings(_env_file=None, env="test", auth_test_accounts=json.dumps(accounts))
    return AuthService(settings)


def test_successful_authentication_issues_random_token_for_stable_identity(
    auth_service: AuthService,
) -> None:
    token, identity = auth_service.authenticate("traveler1", "correct-password", "127.0.0.1")

    assert len(token) >= 40
    assert identity.owner_id == "user-1"
    assert auth_service.identify(token) == identity
    assert token not in auth_service._sessions


def test_unknown_user_and_wrong_password_have_same_public_error(auth_service: AuthService) -> None:
    for username in ["unknown", "traveler1"]:
        with pytest.raises(ServiceError) as exc_info:
            auth_service.authenticate(username, "wrong-password", "127.0.0.1")
        assert exc_info.value.code is ErrorCode.UNAUTHORIZED


def test_session_expiry_and_logout_revoke_immediately(
    auth_service: AuthService, monkeypatch: pytest.MonkeyPatch
) -> None:
    token, identity = auth_service.authenticate("traveler1", "correct-password", "127.0.0.1")
    created = auth_service._sessions[next(iter(auth_service._sessions))][1] - SESSION_TTL_SECONDS
    monkeypatch.setattr(
        "app.modules.auth.service.time.monotonic", lambda: created + SESSION_TTL_SECONDS
    )
    assert auth_service.identify(token) is None

    monkeypatch.setattr("app.modules.auth.service.time.monotonic", lambda: created)
    token, identity = auth_service.authenticate("traveler1", "correct-password", "127.0.0.1")
    auth_service.logout(token)
    assert auth_service.identify(token) is None
    assert identity.owner_id == "user-1"


def test_failed_attempts_are_limited_per_username_and_client(auth_service: AuthService) -> None:
    for _ in range(5):
        with pytest.raises(ServiceError) as exc_info:
            auth_service.authenticate("traveler1", "wrong-password", "127.0.0.1")
        assert exc_info.value.code is ErrorCode.UNAUTHORIZED

    with pytest.raises(ServiceError) as limited:
        auth_service.authenticate("traveler1", "correct-password", "127.0.0.1")
    assert limited.value.code is ErrorCode.RATE_LIMITED

    token, identity = auth_service.authenticate("traveler1", "correct-password", "127.0.0.2")
    assert auth_service.identify(token) == identity
