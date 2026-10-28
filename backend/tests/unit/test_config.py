from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import ProviderConfig, Settings, get_settings
from app.core.contracts import ResultState


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults_are_localhost_only_and_have_no_secret() -> None:
    settings = Settings(_env_file=None)

    assert settings.env == "development"
    assert settings.allowed_origins == (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    )
    assert settings.model_api_key is None
    assert "MODEL_API_KEY" not in repr(settings)


def test_environment_values_are_loaded_from_app_prefixed_variables(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("APP_ALLOWED_ORIGINS", '["http://localhost:4173"]')
    monkeypatch.setenv("APP_MODEL_NAME", "fixture-model")
    monkeypatch.setenv("APP_MODEL_API_KEY", "fake-secret-for-test")

    settings = Settings(_env_file=None)

    assert settings.env == "test"
    assert settings.allowed_origins == ("http://localhost:4173",)
    assert settings.model_name == "fixture-model"
    assert settings.model_api_key is not None
    assert settings.model_api_key.get_secret_value() == "fake-secret-for-test"
    assert "fake-secret-for-test" not in repr(settings)
    assert "fake-secret-for-test" not in settings.model_dump_json()


@pytest.mark.parametrize(
    "origins",
    [
        '["*"]',
        '["http://localhost:5173/path"]',
        '["http://user:pass@localhost:5173"]',
        '["http://localhost:5173?token=secret"]',
        '["HTTP://localhost:5173"]',
        '["http://LOCALHOST:5173"]',
        '["ftp://localhost:5173"]',
        '["http://localhost:bad"]',
        '["http://localhost:5173", "http://localhost:5173"]',
    ],
)
def test_invalid_origins_fail_closed(origins: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, allowed_origins=origins)


def test_production_rejects_plain_http_origins() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, env="production", allowed_origins=("http://localhost:5173",))


def test_production_accepts_explicit_https_origins() -> None:
    settings = Settings(_env_file=None, env="production", allowed_origins=("https://example.com",))

    assert settings.allowed_origins == ("https://example.com",)


def test_provider_with_missing_required_values_reports_unconfigured() -> None:
    missing = ProviderConfig()
    configured = ProviderConfig(
        endpoint="https://provider.example.com/api",
        api_key="fixture-key",
    )

    assert missing.is_configured is False
    assert missing.missing_state is ResultState.UNCONFIGURED
    assert configured.is_configured is True
    assert configured.missing_state is None
    assert "fixture-key" not in repr(configured)


def test_invalid_setting_error_does_not_echo_model_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_MODEL_API_KEY", "secret-value-that-must-not-echo")
    monkeypatch.setenv("APP_ALLOWED_ORIGINS", '["*"]')

    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)

    assert "secret-value-that-must-not-echo" not in str(exc_info.value)


def test_settings_load_explicit_local_env_file(tmp_path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'APP_ENV="test"\nAPP_ALLOWED_ORIGINS=["http://localhost:4173"]\n',
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.env == "test"
    assert settings.allowed_origins == ("http://localhost:4173",)

