from __future__ import annotations

from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit, urlunsplit

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.contracts import ContractModel, ResultState

EnvironmentName = Literal["development", "test", "production"]


class ProviderConfig(ContractModel):
    """Optional provider credentials; values are never included in public responses."""

    endpoint: AnyHttpUrl | None = None
    api_key: SecretStr | None = None

    @property
    def is_configured(self) -> bool:
        return (
            self.endpoint is not None
            and self.api_key is not None
            and bool(self.api_key.get_secret_value())
        )

    @property
    def missing_state(self) -> ResultState | None:
        """Return the public state only when a provider cannot be used yet."""
        return None if self.is_configured else ResultState.UNCONFIGURED


class Settings(BaseSettings):
    """Validated process settings loaded from APP_* variables and a local .env file."""

    model_config = SettingsConfigDict(
        env_file=(".env",),
        env_file_encoding="utf-8",
        env_prefix="APP_",
        extra="ignore",
        case_sensitive=False,
        validate_assignment=True,
    )

    env: EnvironmentName = "development"
    allowed_origins: tuple[str, ...] = (
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    model_name: str | None = Field(default=None, min_length=1, max_length=120)
    model_api_key: SecretStr | None = None

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def reject_empty_origin_list(cls, value: object) -> object:
        if value is None:
            raise ValueError("APP_ALLOWED_ORIGINS must not be null.")
        if isinstance(value, str) and not value.strip():
            raise ValueError("APP_ALLOWED_ORIGINS must not be empty.")
        return value

    @field_validator("allowed_origins")
    @classmethod
    def validate_origins(cls, origins: tuple[str, ...]) -> tuple[str, ...]:
        if not origins:
            raise ValueError("At least one allowed origin is required.")

        normalized: list[str] = []
        for origin in origins:
            if not isinstance(origin, str) or origin != origin.strip() or not origin:
                raise ValueError(
                    "Origins must be non-empty strings without surrounding whitespace."
                )
            if origin == "*":
                raise ValueError("Wildcard CORS origins are not allowed.")
            parts = urlsplit(origin)
            if parts.scheme not in {"http", "https"} or not parts.netloc:
                raise ValueError("Origins must use an explicit http or https scheme.")
            if parts.username is not None or parts.password is not None:
                raise ValueError("Origins must not contain credentials.")
            if parts.path or parts.query or parts.fragment:
                raise ValueError("Origins must not contain a path, query, or fragment.")
            if parts.hostname is None or parts.hostname != parts.hostname.lower():
                raise ValueError("Origins must use a lowercase hostname.")
            try:
                _ = parts.port
            except ValueError as exc:
                raise ValueError("Origins must use a valid port.") from exc
            canonical = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
            if canonical != origin:
                raise ValueError("Origin is not in canonical form.")
            normalized.append(canonical)

        if len(set(normalized)) != len(normalized):
            raise ValueError("Allowed origins must be unique.")
        return tuple(normalized)

    @model_validator(mode="after")
    def validate_environment_security(self) -> Settings:
        if self.env == "production" and any(
            not origin.startswith("https://") for origin in self.allowed_origins
        ):
            raise ValueError("Production origins must all use HTTPS.")
        return self

    def provider(
        self, *, endpoint: AnyHttpUrl | None = None, api_key: SecretStr | None = None
    ) -> ProviderConfig:
        return ProviderConfig(endpoint=endpoint, api_key=api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
