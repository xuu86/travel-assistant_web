from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.modules.auth.credentials import hash_password

ORIGIN = "http://testserver"


def auth_settings(*, env: str = "test", accounts: bool = True) -> Settings:
    records = [
        {
            "username": f"traveler{i}",
            "owner_id": f"user-{i}",
            "display_name": f"旅行用户{i}",
            "password_hash": hash_password("test-password"),
        }
        for i in range(1, 6)
    ]
    return Settings(
        _env_file=None,
        env=env,
        allowed_origins=("https://travel.example.com",) if env == "production" else (ORIGIN,),
        auth_test_accounts=json.dumps(records) if accounts else None,
    )


def test_session_is_guest_then_login_and_logout_revokes_cookie() -> None:
    client = TestClient(create_app(auth_settings()))

    guest = client.get("/api/v1/auth/session")
    assert guest.status_code == 200
    assert guest.json() == {"identity_type": "guest", "owner_id": None, "display_name": None}

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "traveler1", "password": "test-password"},
        headers={"Origin": ORIGIN},
    )
    assert login.status_code == 200
    assert login.json() == {
        "identity_type": "account",
        "owner_id": "user-1",
        "display_name": "旅行用户1",
    }
    cookie = login.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" not in cookie

    session = client.get("/api/v1/auth/session")
    assert session.json()["owner_id"] == "user-1"
    assert "test-password" not in session.text

    logout = client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN})
    assert logout.status_code == 204
    assert client.get("/api/v1/auth/session").json()["identity_type"] == "guest"


def test_invalid_username_and_password_return_same_safe_error() -> None:
    client = TestClient(create_app(auth_settings()))
    headers = {"Origin": ORIGIN}
    unknown = client.post(
        "/api/v1/auth/login",
        json={"username": "unknown-user", "password": "wrong-password"},
        headers=headers,
    )
    incorrect = client.post(
        "/api/v1/auth/login",
        json={"username": "traveler1", "password": "wrong-password"},
        headers=headers,
    )

    assert unknown.status_code == incorrect.status_code == 401
    assert unknown.json()["code"] == incorrect.json()["code"] == "UNAUTHORIZED"
    assert unknown.json()["message"] == incorrect.json()["message"]
    assert unknown.json()["retryable"] == incorrect.json()["retryable"]
    assert "unknown-user" not in unknown.text
    assert "wrong-password" not in incorrect.text


def test_login_requires_same_origin_and_does_not_echo_request_body() -> None:
    client = TestClient(create_app(auth_settings()))
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "traveler1", "password": "private-sentinel-password"},
        headers={"Origin": "http://evil.example"},
    )

    assert response.status_code == 403
    assert "private-sentinel-password" not in response.text
    assert client.get("/api/v1/auth/session").json()["identity_type"] == "guest"


def test_missing_accounts_keeps_guest_session_and_reports_login_unconfigured() -> None:
    client = TestClient(create_app(auth_settings(accounts=False)))

    assert client.get("/api/v1/auth/session").json()["identity_type"] == "guest"
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "traveler1", "password": "test-password"},
        headers={"Origin": ORIGIN},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "UNCONFIGURED"


def test_production_cookie_is_secure() -> None:
    client = TestClient(create_app(auth_settings(env="production")), base_url="https://testserver")
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "traveler1", "password": "test-password"},
        headers={"Origin": "https://testserver"},
    )

    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


def test_logout_is_idempotent_and_revoked_cookie_cannot_reauthenticate() -> None:
    client = TestClient(create_app(auth_settings()))
    client.post(
        "/api/v1/auth/login",
        json={"username": "traveler1", "password": "test-password"},
        headers={"Origin": ORIGIN},
    )
    token = client.cookies.get("travel_session")

    assert client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN}).status_code == 204
    client.cookies.set("travel_session", token)
    assert client.get("/api/v1/auth/session").json()["identity_type"] == "guest"
    assert client.post("/api/v1/auth/logout", headers={"Origin": ORIGIN}).status_code == 204
