from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_assistant_provider_is_unconfigured_without_all_required_values() -> None:
    settings = Settings(_env_file=None, model_api_key="test-key", model_name="test-model")

    assert settings.assistant_model_configured is False
    assert settings.model_base_url is None


def test_assistant_provider_requires_endpoint_key_and_model_name() -> None:
    settings = Settings(
        _env_file=None,
        model_base_url="https://model.example.com/v1",
        model_api_key="test-key",
        model_name="test-model",
    )

    assert settings.assistant_model_configured is True
    assert settings.model_timeout_seconds == 30
    assert "test-key" not in repr(settings)
    assert "test-key" not in settings.model_dump_json()


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://user:password@model.example.com/v1",
        "https://model.example.com/v1?token=secret",
        "https://model.example.com/v1#fragment",
    ],
)
def test_assistant_model_base_url_rejects_non_http_or_embedded_credentials(url: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, model_base_url=url)


def test_assistant_model_timeout_is_bounded() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, model_timeout_seconds=0)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, model_timeout_seconds=31)


def test_production_model_endpoint_requires_https() -> None:
    with pytest.raises(ValidationError, match="Production model endpoints must use HTTPS"):
        Settings(
            _env_file=None,
            env="production",
            allowed_origins=("https://travel.example.com",),
            model_base_url="http://model.example.com/v1",
        )

    settings = Settings(
        _env_file=None,
        env="production",
        allowed_origins=("https://travel.example.com",),
        model_base_url="https://model.example.com/v1",
    )
    assert str(settings.model_base_url).startswith("https://")


def test_assistant_model_settings_use_app_prefixed_environment_variables(monkeypatch) -> None:
    monkeypatch.setenv("APP_MODEL_BASE_URL", "https://model.example.com/v1")
    monkeypatch.setenv("APP_MODEL_API_KEY", "fixture-key")
    monkeypatch.setenv("APP_MODEL_NAME", "fixture-model")
    monkeypatch.setenv("APP_MODEL_TIMEOUT_SECONDS", "12")

    settings = Settings(_env_file=None)

    assert settings.assistant_model_configured is True
    assert settings.model_timeout_seconds == 12
