from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_registration_persists_and_rejects_duplicate(tmp_path):
    settings = Settings(env="test", auth_database_path=str(tmp_path / "accounts.sqlite3"))
    payload = {"username": "traveler42", "password": "a-long-test-password"}
    headers = {"origin": "http://testserver"}
    with TestClient(create_app(settings)) as client:
        assert (
            client.post("/api/v1/auth/register", json=payload, headers=headers).status_code == 201
        )
        assert (
            client.post("/api/v1/auth/register", json=payload, headers=headers).status_code == 422
        )
        assert (
            client.post(
                "/api/v1/auth/register", json={**payload, "password": "short"}, headers=headers
            ).status_code
            == 422
        )
        assert client.post("/api/v1/auth/login", json=payload, headers=headers).status_code == 200
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/v1/auth/login", json=payload, headers=headers).status_code == 200
    assert payload["password"].encode() not in (tmp_path / "accounts.sqlite3").read_bytes()
