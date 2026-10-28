from __future__ import annotations

import logging
from uuid import UUID

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.contracts import ErrorCode
from app.core.errors import ServiceError
from app.main import create_app


def make_test_app():
    return create_app(
        Settings(
            _env_file=None,
            env="test",
            allowed_origins=("http://localhost:4173",),
        )
    )


def test_request_id_is_unique_and_public_errors_match_response_header() -> None:
    client = TestClient(make_test_app())

    first = client.get("/api/foundation/cities")
    second = client.get("/api/foundation/cities")
    missing = client.get("/api/foundation/cities/not-registered")

    first_id = UUID(first.headers["x-request-id"])
    second_id = UUID(second.headers["x-request-id"])
    missing_id = UUID(missing.headers["x-request-id"])
    assert first_id != second_id
    assert missing.status_code == 404
    assert missing.json()["code"] == ErrorCode.NOT_FOUND
    assert missing.json()["request_id"] == str(missing_id)


def test_cors_allows_only_the_configured_exact_origin() -> None:
    client = TestClient(make_test_app())

    allowed = client.get("/api/health", headers={"Origin": "http://localhost:4173"})
    denied = client.get("/api/health", headers={"Origin": "http://evil.example"})
    denied_preflight = client.options(
        "/api/foundation/cities",
        headers={
            "Origin": "http://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:4173"
    assert "access-control-allow-origin" not in denied.headers
    assert denied_preflight.status_code == 400
    assert "access-control-allow-origin" not in denied_preflight.headers


def test_validation_error_uses_safe_public_error_and_request_id() -> None:
    app = make_test_app()

    def integer_value(value: int) -> dict[str, int]:
        return {"value": value}

    app.add_api_route("/__test__/integer", integer_value, methods=["GET"])
    response = TestClient(app).get("/__test__/integer?value=not-an-integer")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == ErrorCode.VALIDATION_ERROR
    assert body["request_id"] == response.headers["x-request-id"]
    assert "detail" not in body
    assert "not-an-integer" not in response.text


def test_service_error_uses_curated_public_error() -> None:
    app = make_test_app()

    def provider_failure() -> None:
        raise ServiceError(ErrorCode.PROVIDER_UNAVAILABLE)

    app.add_api_route("/__test__/provider", provider_failure, methods=["GET"])
    response = TestClient(app).get("/__test__/provider")

    assert response.status_code == 503
    assert response.json()["code"] == ErrorCode.PROVIDER_UNAVAILABLE
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "traceback" not in response.text.lower()


def test_unexpected_exception_is_sanitized_and_logs_only_request_metadata(caplog) -> None:
    app = make_test_app()
    sentinel = "fake-secret-that-must-never-be-logged"

    def unexpected_failure() -> None:
        raise RuntimeError(f"{sentinel}; C:\\private\\order.pdf")

    app.add_api_route("/__test__/unexpected", unexpected_failure, methods=["GET"])
    caplog.set_level(logging.INFO, logger="app.request")
    response = TestClient(app).get("/__test__/unexpected")

    assert response.status_code == 500
    assert response.json()["code"] == ErrorCode.INTERNAL_ERROR
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert sentinel not in response.text
    assert "private" not in response.text
    assert sentinel not in caplog.text
    completion = next(record for record in caplog.records if record.message == "request_complete")
    assert completion.request_id == response.headers["x-request-id"]
    assert completion.status_code == 500
    assert completion.route_name == "unexpected_failure"
