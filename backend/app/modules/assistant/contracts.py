from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, TypeAdapter, field_validator, model_validator

from app.core.contracts import ContractModel, EvidenceState, PublicError, ResultState, SourceRef

ChatRole = Literal["user", "assistant"]
EvidenceKind = Literal["weather", "transport", "hotel", "activity", "attraction"]
TripPace = Literal["relaxed", "balanced", "full"]
TransportMode = Literal["any", "flight", "rail", "high_speed"]
AssistantState = Literal[
    ResultState.LIVE,
    ResultState.UNCONFIGURED,
    ResultState.RATE_LIMITED,
    ResultState.UNAVAILABLE,
    ResultState.POLICY_UNAVAILABLE,
]

_CONTROL_CHARACTER = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _trim_text(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank.")
    if _CONTROL_CHARACTER.search(normalized):
        raise ValueError(f"{field_name} must not contain control characters.")
    return normalized


def _parse_date(value: object) -> object:
    if isinstance(value, datetime):
        raise ValueError("Date must not include a time.")
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return value
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValueError("Date must use YYYY-MM-DD format.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Date must be a valid calendar date.") from exc


class ChatMessage(ContractModel):
    role: ChatRole
    content: str = Field(min_length=1, max_length=4_000)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        return _trim_text(value, field_name="content")


class TripContext(ContractModel):
    destination: str | None = Field(default=None, min_length=1, max_length=80)
    start_date: date | None = None
    end_date: date | None = None
    travelers: int | None = Field(default=None, ge=1)
    budget_fen: int | None = Field(default=None, ge=0)
    interests: list[str] = Field(default_factory=list, max_length=10)
    pace: TripPace | None = None
    transport_mode: TransportMode | None = None

    @field_validator("destination")
    @classmethod
    def normalize_destination(cls, value: str | None) -> str | None:
        return _trim_text(value, field_name="destination") if value is not None else None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_dates(cls, value: object) -> object:
        return _parse_date(value)

    @field_validator("interests")
    @classmethod
    def normalize_interests(cls, value: list[str]) -> list[str]:
        normalized = [_trim_text(item, field_name="interest") for item in value]
        if len(set(normalized)) != len(normalized):
            raise ValueError("interests must not contain duplicates.")
        return normalized

    @model_validator(mode="after")
    def validate_date_range(self) -> TripContext:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date.")
        return self


class AssistantEvidence(ContractModel):
    evidence_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    kind: EvidenceKind
    summary: str = Field(min_length=1, max_length=2_000)
    state: Literal[ResultState.LIVE, ResultState.PARTIAL]
    source: SourceRef

    @field_validator("source", mode="before")
    @classmethod
    def parse_json_source(cls, value: object) -> object:
        if isinstance(value, dict):
            return TypeAdapter(SourceRef).validate_json(json.dumps(value))
        return value

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        return _trim_text(value, field_name="summary")

    @model_validator(mode="after")
    def mark_source_user_provided(self) -> AssistantEvidence:
        # Evidence is submitted by the browser and cannot establish provider truth.
        self.source = self.source.model_copy(update={"evidence_state": EvidenceState.USER_PROVIDED})
        return self


class ChatRequest(ContractModel):
    message: str = Field(min_length=1, max_length=2_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    include_trip_context: bool = False
    trip_context: TripContext | None = None
    evidence: list[AssistantEvidence] = Field(default_factory=list, max_length=20)

    @field_validator("message")
    @classmethod
    def normalize_message(cls, value: str) -> str:
        return _trim_text(value, field_name="message")

    @model_validator(mode="after")
    def validate_history_size(self) -> ChatRequest:
        if len(self.message) + sum(len(item.content) for item in self.history) > 12_000:
            raise ValueError("message and history exceed the total character limit.")
        evidence_ids = [item.evidence_id for item in self.evidence]
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence_id values must be unique.")
        return self


class CandidatePatch(ContractModel):
    destination: str | None = Field(default=None, min_length=1, max_length=80)
    start_date: date | None = None
    end_date: date | None = None
    travelers: int | None = Field(default=None, ge=1)
    budget_fen: int | None = Field(default=None, ge=0)
    interests: list[str] | None = Field(default=None, max_length=10)
    pace: TripPace | None = None
    transport_mode: TransportMode | None = None

    @field_validator("destination")
    @classmethod
    def normalize_destination(cls, value: str | None) -> str | None:
        return _trim_text(value, field_name="destination") if value is not None else None

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def parse_dates(cls, value: object) -> object:
        return _parse_date(value)

    @field_validator("interests")
    @classmethod
    def normalize_interests(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [_trim_text(item, field_name="interest") for item in value]
        if len(set(normalized)) != len(normalized):
            raise ValueError("interests must not contain duplicates.")
        return normalized

    @model_validator(mode="after")
    def validate_candidate_patch(self) -> CandidatePatch:
        if not self.model_fields_set:
            raise ValueError("candidate patch must contain at least one change.")
        if any(getattr(self, field_name) is None for field_name in self.model_fields_set):
            raise ValueError("candidate patch values must not be null.")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date.")
        return self


class AssistantResponse(ContractModel):
    state: AssistantState
    request_id: UUID
    message: str = Field(max_length=240)
    reply: str = Field(default="", max_length=4_000)
    candidate_patch: CandidatePatch | None = None
    sources: list[SourceRef] = Field(default_factory=list, max_length=20)
    error: PublicError | None = None

    @model_validator(mode="after")
    def validate_response_state(self) -> AssistantResponse:
        if self.state is ResultState.LIVE:
            if not self.reply.strip():
                raise ValueError("A live assistant response must contain a reply.")
            if self.error is not None:
                raise ValueError("A live assistant response must not contain an error.")
        elif self.reply or self.candidate_patch is not None or self.sources or self.error is None:
            raise ValueError("A failed assistant response must not contain generated content.")
        if self.error is not None and self.error.request_id not in (None, self.request_id):
            raise ValueError("Error request_id must match the assistant response.")
        return self
