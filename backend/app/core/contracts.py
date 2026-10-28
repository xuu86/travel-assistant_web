from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator, model_validator


class ResultState(StrEnum):
    LIVE = "live"
    PARTIAL = "partial"
    EMPTY = "empty"
    DEMO = "demo"
    UNCONFIGURED = "unconfigured"
    NO_COVERAGE = "no_coverage"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    POLICY_UNAVAILABLE = "policy_unavailable"


class EvidenceState(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    USER_PROVIDED = "user_provided"
    ESTIMATE = "estimate"
    DEMO = "demo"
    UNKNOWN = "unknown"


class ErrorCode(StrEnum):
    UNCONFIGURED = "UNCONFIGURED"
    NO_COVERAGE = "NO_COVERAGE"
    RATE_LIMITED = "RATE_LIMITED"
    PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
    POLICY_UNAVAILABLE = "POLICY_UNAVAILABLE"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    CONFIG_INVALID = "CONFIG_INVALID"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def normalize_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must include a timezone.")
    return value.astimezone(UTC)


class DateRange(ContractModel):
    start: date
    end: date

    @model_validator(mode="after")
    def validate_order(self) -> DateRange:
        if self.end < self.start:
            raise ValueError("Date range end must not precede start.")
        return self


class Coverage(ContractModel):
    requested: DateRange
    covered: list[DateRange] = Field(default_factory=list)
    missing: list[DateRange] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_ranges_within_request(self) -> Coverage:
        request_start = self.requested.start
        request_end = self.requested.end
        for coverage_range in [*self.covered, *self.missing]:
            if coverage_range.start < request_start or coverage_range.end > request_end:
                raise ValueError("Coverage ranges must stay within the requested range.")
        return self


class SourceRef(ContractModel):
    source_id: str = Field(min_length=1, max_length=120, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:-]*$")
    display_name: str = Field(min_length=1, max_length=160)
    url: AnyHttpUrl | None = None
    retrieved_at: datetime
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    attribution: str | None = Field(default=None, max_length=500)
    evidence_state: EvidenceState = EvidenceState.UNKNOWN

    @field_validator("url", mode="before")
    @classmethod
    def sanitize_public_url(cls, value: object) -> object:
        if value is None:
            return None
        parts = urlsplit(str(value))
        if parts.username is not None or parts.password is not None:
            raise ValueError("Public source URLs must not contain credentials.")
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))

    @field_validator("retrieved_at", "valid_from", "valid_to")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_aware_utc(value)

    @model_validator(mode="after")
    def validate_validity(self) -> SourceRef:
        if self.valid_from and self.valid_to and self.valid_to < self.valid_from:
            raise ValueError("Source validity end must not precede its start.")
        return self


class MoneyAmount(ContractModel):
    amount_fen: int | None = Field(default=None, ge=0)
    currency_code: str = Field(default="CNY", pattern=r"^[A-Z]{3}$")


class PublicError(ContractModel):
    code: ErrorCode
    message: str = Field(min_length=1, max_length=240)
    retryable: bool
    request_id: UUID | None = None





class ResultEnvelope[T](ContractModel):
    state: ResultState
    items: list[T] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    queried_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    request_id: UUID
    message: str = Field(default="", max_length=240)
    coverage: Coverage | None = None
    error: PublicError | None = None

    @field_validator("queried_at")
    @classmethod
    def normalize_query_time(cls, value: datetime) -> datetime:
        return normalize_aware_utc(value)

    @model_validator(mode="after")
    def validate_state_consistency(self) -> ResultEnvelope[T]:
        if self.state is ResultState.EMPTY and self.items:
            raise ValueError("An empty result cannot contain items.")
        if self.state is ResultState.LIVE and not self.items:
            raise ValueError("Use the empty state when a live query returns no items.")
        if self.state in {
            ResultState.UNCONFIGURED,
            ResultState.NO_COVERAGE,
            ResultState.RATE_LIMITED,
            ResultState.UNAVAILABLE,
            ResultState.POLICY_UNAVAILABLE,
        } and self.items:
            raise ValueError("A failed or unavailable result cannot contain items.")
        if self.error is not None and self.error.request_id not in (None, self.request_id):
            raise ValueError("Nested error request_id must match the result request_id.")
        return self

