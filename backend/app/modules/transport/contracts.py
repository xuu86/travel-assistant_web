from __future__ import annotations

import math
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator, model_validator

from app.core.contracts import (
    ContractModel,
    EvidenceState,
    ResultEnvelope,
    ResultState,
    SourceRef,
    normalize_aware_utc,
)

FareMode = Literal["flight", "rail"]
RouteMode = Literal["transit", "walking", "taxi"]
PriceBasis = Literal["per_passenger", "party_total", "unknown"]
AmountBasis = Literal["per_passenger", "party_total", "unknown"]
Availability = Literal["available", "unavailable", "unknown"]
InclusionState = Literal["included", "excluded", "unknown"]
PriceScope = Literal["entire_journey", "single_segment", "unknown"]
DurationBasis = Literal["realtime", "scheduled", "typical_estimate", "unknown"]
RouteFareBasis = Literal["per_route", "per_passenger", "meter_estimate", "unknown"]
RouteStepMode = Literal["walking", "bus", "subway", "rail", "taxi", "driving"]

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
_CURRENCY_PATTERN = r"^[A-Z]{3}$"
_OFFER_MISSING_FIELDS = {
    "service_number",
    "departure_at",
    "arrival_at",
    "departure_timezone",
    "arrival_timezone",
    "price_fen",
    "remaining_seats",
    "included_charges",
    "price_basis",
    "price_scope",
    "passenger_count",
    "availability",
}
_ROUTE_MISSING_FIELDS = {
    "distance_m",
    "duration_seconds",
    "steps",
    "geometry_points",
    "fare_amount_fen",
    "duration_basis",
    "fare_basis",
}


def _require_nonblank(value: str | None, *, field_name: str) -> str | None:
    if value is not None and not value.strip():
        raise ValueError(f"{field_name} must not be blank.")
    return value


def _validate_timezone(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("Timezone must be a valid IANA timezone.") from exc
    return value


def _validate_finite(value: float | None) -> float | None:
    if value is not None and not math.isfinite(value):
        raise ValueError("Numeric values must be finite.")
    return value


def _parse_coordinate(value: object) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return float(value)
    return value


def _parse_date(value: object) -> object:
    if isinstance(value, datetime):
        raise ValueError("A calendar date must not include a time.")
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return value
    if (
        len(value) != 10
        or value[4] != "-"
        or value[7] != "-"
        or not (value[:4] + value[5:7] + value[8:]).isdigit()
    ):
        raise ValueError("Date must use YYYY-MM-DD format.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Date must be a valid calendar date.") from exc


def _parse_datetime(value: object) -> object:
    if not isinstance(value, str):
        return value
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("Datetime must be a valid ISO 8601 value.") from exc
    return normalize_aware_utc(parsed)


def _validate_missing_fields(fields: list[str], *, allowed: set[str]) -> None:
    if len(fields) != len(set(fields)):
        raise ValueError("missing_fields must not contain duplicates.")
    if set(fields).difference(allowed):
        raise ValueError("missing_fields contains an unknown transport field.")


class PlaceRef(ContractModel):
    place_id: str | None = Field(
        default=None, min_length=1, max_length=160, pattern=_IDENTIFIER_PATTERN
    )
    display_name: str = Field(min_length=1, max_length=240)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    coordinate_system: Literal["WGS84"] = "WGS84"

    @field_validator("place_id", "display_name")
    @classmethod
    def reject_blank_names(cls, value: str | None, info) -> str | None:
        return _require_nonblank(value, field_name=info.field_name)

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def parse_coordinates(cls, value: object) -> object:
        return _parse_coordinate(value)

    @field_validator("latitude", "longitude")
    @classmethod
    def reject_non_finite_coordinates(cls, value: float | None) -> float | None:
        return _validate_finite(value)

    @model_validator(mode="after")
    def validate_coordinate_pair(self) -> PlaceRef:
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Latitude and longitude must either both be present or both be null.")
        return self


def same_place(first: PlaceRef, second: PlaceRef) -> bool:
    """Conservatively reject identical query endpoints when the supplied identity permits it."""
    if first.place_id is not None and second.place_id is not None:
        return first.place_id == second.place_id
    if first.latitude is not None and second.latitude is not None:
        return first.latitude == second.latitude and first.longitude == second.longitude
    return first.display_name.strip().casefold() == second.display_name.strip().casefold()


class FareQuery(ContractModel):
    origin: PlaceRef
    destination: PlaceRef
    mode: FareMode
    travel_date: date
    passenger_count: int = Field(ge=1)

    @field_validator("travel_date", mode="before")
    @classmethod
    def parse_travel_date(cls, value: object) -> object:
        return _parse_date(value)

    @model_validator(mode="after")
    def validate_distinct_places(self) -> FareQuery:
        if same_place(self.origin, self.destination):
            raise ValueError("origin and destination must identify different places.")
        return self


class RouteQuery(ContractModel):
    origin: PlaceRef
    destination: PlaceRef
    mode: RouteMode
    depart_at: datetime | None = None

    @field_validator("depart_at", mode="before")
    @classmethod
    def parse_departure_time(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, datetime):
            return normalize_aware_utc(value)
        return _parse_datetime(value)


class FareSegment(ContractModel):
    segment_id: str = Field(min_length=1, max_length=120, pattern=_IDENTIFIER_PATTERN)
    origin_name: str | None = Field(default=None, min_length=1, max_length=240)
    destination_name: str | None = Field(default=None, min_length=1, max_length=240)
    departure_at: datetime | None = None
    arrival_at: datetime | None = None
    departure_timezone: str | None = None
    arrival_timezone: str | None = None
    service_number: str | None = Field(default=None, max_length=80)
    operating_carrier: str | None = Field(default=None, max_length=160)
    transfer_place: str | None = Field(default=None, max_length=240)

    @field_validator(
        "origin_name",
        "destination_name",
        "service_number",
        "operating_carrier",
        "transfer_place",
    )
    @classmethod
    def reject_blank_optional_text(cls, value: str | None, info) -> str | None:
        return _require_nonblank(value, field_name=info.field_name)

    @field_validator("departure_at", "arrival_at", mode="before")
    @classmethod
    def parse_segment_times(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, datetime):
            return normalize_aware_utc(value)
        return _parse_datetime(value)

    @field_validator("departure_timezone", "arrival_timezone")
    @classmethod
    def validate_segment_timezones(cls, value: str | None) -> str | None:
        return _validate_timezone(value)

    @model_validator(mode="after")
    def validate_time_order(self) -> FareSegment:
        if (
            self.departure_at is not None
            and self.arrival_at is not None
            and self.arrival_at < self.departure_at
        ):
            raise ValueError("arrival_at must not precede departure_at.")
        return self


class ChargeComponent(ContractModel):
    charge_type: str = Field(min_length=1, max_length=80, pattern=_IDENTIFIER_PATTERN)
    display_name: str = Field(min_length=1, max_length=160)
    inclusion_state: InclusionState
    amount_fen: int | None = Field(default=None, ge=0)
    currency_code: str = Field(default="CNY", pattern=_CURRENCY_PATTERN)
    amount_basis: AmountBasis

    @field_validator("display_name")
    @classmethod
    def reject_blank_display_name(cls, value: str) -> str:
        return _require_nonblank(value, field_name="display_name") or value

    @model_validator(mode="after")
    def validate_amount_currency(self) -> ChargeComponent:
        if self.amount_fen is not None and self.currency_code != "CNY":
            raise ValueError("amount_fen represents CNY only.")
        return self


class FareOffer(ContractModel):
    offer_id: str = Field(min_length=1, max_length=120, pattern=_IDENTIFIER_PATTERN)
    source_id: str = Field(min_length=1, max_length=120, pattern=_IDENTIFIER_PATTERN)
    mode: FareMode
    travel_date: date
    segments: list[FareSegment] = Field(min_length=1)
    service_number: str | None = Field(default=None, max_length=80)
    departure_at: datetime | None = None
    arrival_at: datetime | None = None
    departure_timezone: str | None = None
    arrival_timezone: str | None = None
    origin_name: str = Field(min_length=1, max_length=240)
    destination_name: str = Field(min_length=1, max_length=240)
    price_fen: int | None = Field(default=None, ge=0)
    currency_code: str = Field(default="CNY", pattern=_CURRENCY_PATTERN)
    price_basis: PriceBasis
    price_scope: PriceScope = "unknown"
    price_segment_id: str | None = Field(default=None, max_length=120, pattern=_IDENTIFIER_PATTERN)
    passenger_count: int | None = Field(default=None, ge=1)
    included_charges: list[ChargeComponent] = Field(default_factory=list)
    availability: Availability = "unknown"
    remaining_seats: int | None = Field(default=None, ge=0)
    evidence_state: EvidenceState
    missing_fields: list[str] = Field(default_factory=list)

    @field_validator("travel_date", mode="before")
    @classmethod
    def parse_offer_travel_date(cls, value: object) -> object:
        return _parse_date(value)

    @field_validator("service_number", "origin_name", "destination_name")
    @classmethod
    def reject_blank_offer_text(cls, value: str | None, info) -> str | None:
        return _require_nonblank(value, field_name=info.field_name)

    @field_validator("departure_at", "arrival_at", mode="before")
    @classmethod
    def parse_offer_times(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, datetime):
            return normalize_aware_utc(value)
        return _parse_datetime(value)

    @field_validator("departure_timezone", "arrival_timezone")
    @classmethod
    def validate_offer_timezones(cls, value: str | None) -> str | None:
        return _validate_timezone(value)

    @model_validator(mode="after")
    def validate_offer_semantics(self) -> FareOffer:
        if self.price_fen is not None and self.currency_code != "CNY":
            raise ValueError("price_fen represents CNY only.")
        if self.price_basis == "party_total" and self.passenger_count is None:
            raise ValueError("A party_total price must identify its passenger_count.")
        if len(self.segments) > 1 and self.service_number is not None:
            raise ValueError("A multi-segment offer must not invent one top-level service_number.")
        if (
            len(self.segments) == 1
            and self.service_number is not None
            and self.segments[0].service_number is not None
            and self.service_number != self.segments[0].service_number
        ):
            raise ValueError("A direct offer service_number must match its segment.")
        segment_ids = {segment.segment_id for segment in self.segments}
        if self.price_scope == "single_segment":
            if self.price_segment_id not in segment_ids:
                raise ValueError("A single-segment price must identify the priced segment.")
        elif self.price_segment_id is not None:
            raise ValueError("price_segment_id is only valid for a single-segment price.")

        first_segment = self.segments[0]
        last_segment = self.segments[-1]
        if self.departure_at != first_segment.departure_at:
            raise ValueError("departure_at must match the first segment departure time.")
        if self.arrival_at != last_segment.arrival_at:
            raise ValueError("arrival_at must match the last segment arrival time.")
        if self.departure_timezone != first_segment.departure_timezone:
            raise ValueError("departure_timezone must match the first segment timezone.")
        if self.arrival_timezone != last_segment.arrival_timezone:
            raise ValueError("arrival_timezone must match the last segment timezone.")

        required_missing = {
            field_name
            for field_name in (
                "departure_at",
                "arrival_at",
                "departure_timezone",
                "arrival_timezone",
                "price_fen",
                "remaining_seats",
            )
            if getattr(self, field_name) is None
        }
        if len(self.segments) == 1 and self.service_number is None:
            required_missing.add("service_number")
        if self.price_basis == "unknown":
            required_missing.add("price_basis")
        if self.price_scope == "unknown":
            required_missing.add("price_scope")
        if self.passenger_count is None:
            required_missing.add("passenger_count")
        if self.availability == "unknown":
            required_missing.add("availability")
        if not self.included_charges:
            required_missing.add("included_charges")
        _validate_missing_fields(self.missing_fields, allowed=_OFFER_MISSING_FIELDS)
        if required_missing.difference(self.missing_fields):
            raise ValueError("missing_fields must identify absent fare facts.")
        return self


class GeometryPoint(ContractModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    coordinate_system: Literal["WGS84"] = "WGS84"

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def parse_point_coordinates(cls, value: object) -> object:
        return _parse_coordinate(value)

    @field_validator("latitude", "longitude")
    @classmethod
    def reject_non_finite_point(cls, value: float) -> float:
        return _validate_finite(value) or value


class RouteStep(ContractModel):
    instruction: str | None = Field(default=None, max_length=1000)
    step_mode: RouteStepMode | None = None
    distance_m: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    start_latitude: float | None = Field(default=None, ge=-90, le=90)
    start_longitude: float | None = Field(default=None, ge=-180, le=180)
    end_latitude: float | None = Field(default=None, ge=-90, le=90)
    end_longitude: float | None = Field(default=None, ge=-180, le=180)
    coordinate_system: Literal["WGS84"] = "WGS84"

    @field_validator("instruction")
    @classmethod
    def reject_blank_instruction(cls, value: str | None) -> str | None:
        return _require_nonblank(value, field_name="instruction")

    @field_validator(
        "start_latitude",
        "start_longitude",
        "end_latitude",
        "end_longitude",
        mode="before",
    )
    @classmethod
    def parse_step_coordinates(cls, value: object) -> object:
        return _parse_coordinate(value)

    @field_validator("start_latitude", "start_longitude", "end_latitude", "end_longitude")
    @classmethod
    def reject_non_finite_step_coordinates(cls, value: float | None) -> float | None:
        return _validate_finite(value)

    @model_validator(mode="after")
    def validate_step_coordinate_pairs(self) -> RouteStep:
        if (self.start_latitude is None) != (self.start_longitude is None):
            raise ValueError("Step start latitude and longitude must be paired.")
        if (self.end_latitude is None) != (self.end_longitude is None):
            raise ValueError("Step end latitude and longitude must be paired.")
        return self


class RouteOption(ContractModel):
    route_id: str = Field(min_length=1, max_length=120, pattern=_IDENTIFIER_PATTERN)
    source_id: str = Field(min_length=1, max_length=120, pattern=_IDENTIFIER_PATTERN)
    mode: RouteMode
    origin_name: str = Field(min_length=1, max_length=240)
    destination_name: str = Field(min_length=1, max_length=240)
    distance_m: int | None = Field(default=None, ge=0)
    duration_seconds: int | None = Field(default=None, ge=0)
    duration_basis: DurationBasis
    steps: list[RouteStep] = Field(default_factory=list)
    geometry_points: list[GeometryPoint] | None = Field(default=None, min_length=2)
    fare_amount_fen: int | None = Field(default=None, ge=0)
    currency_code: str = Field(default="CNY", pattern=_CURRENCY_PATTERN)
    fare_basis: RouteFareBasis
    fare_evidence_state: EvidenceState
    evidence_state: EvidenceState
    missing_fields: list[str] = Field(default_factory=list)

    @field_validator("origin_name", "destination_name")
    @classmethod
    def reject_blank_route_names(cls, value: str) -> str:
        return _require_nonblank(value, field_name="route name") or value

    @model_validator(mode="after")
    def validate_route_semantics(self) -> RouteOption:
        if self.duration_seconds is None and self.duration_basis != "unknown":
            raise ValueError("Unknown route duration must use duration_basis='unknown'.")
        if self.duration_seconds is not None and self.duration_basis == "unknown":
            raise ValueError("A known route duration must declare its duration basis.")
        if self.fare_amount_fen is None and self.fare_basis != "unknown":
            raise ValueError("Unknown route fare must use fare_basis='unknown'.")
        if self.fare_amount_fen is None and self.fare_evidence_state is not EvidenceState.UNKNOWN:
            raise ValueError("Unknown route fare must use unknown fare evidence.")
        if self.fare_amount_fen is not None and self.currency_code != "CNY":
            raise ValueError("fare_amount_fen represents CNY only.")
        if self.fare_basis == "meter_estimate":
            if (
                self.mode != "taxi"
                or self.fare_amount_fen is None
                or self.fare_evidence_state is not EvidenceState.ESTIMATE
            ):
                raise ValueError("Meter estimates require an amount and estimate evidence state.")

        required_missing = {
            field_name
            for field_name in (
                "distance_m",
                "duration_seconds",
                "geometry_points",
                "fare_amount_fen",
            )
            if getattr(self, field_name) is None
        }
        if not self.steps:
            required_missing.add("steps")
        if self.duration_basis == "unknown":
            required_missing.add("duration_basis")
        if self.fare_basis == "unknown":
            required_missing.add("fare_basis")
        _validate_missing_fields(self.missing_fields, allowed=_ROUTE_MISSING_FIELDS)
        if required_missing.difference(self.missing_fields):
            raise ValueError("missing_fields must identify absent route facts.")
        return self


class _TransportResult[T](ResultEnvelope[T]):
    @model_validator(mode="after")
    def validate_transport_sources(self) -> _TransportResult[T]:
        if self.state is ResultState.PARTIAL and not self.items:
            raise ValueError("A partial transport result must contain at least one item.")
        if self.state is ResultState.PARTIAL and not any(
            getattr(item, "missing_fields", []) for item in self.items
        ):
            raise ValueError("A partial transport result must identify missing fields.")
        if self.state is ResultState.LIVE and any(
            item.evidence_state is EvidenceState.DEMO
            or getattr(item, "missing_fields", [])
            for item in self.items
        ):
            raise ValueError("Live transport results cannot contain demo or incomplete items.")

        source_map: dict[str, SourceRef] = {}
        for source in self.sources:
            if source.source_id in source_map:
                raise ValueError("Transport result sources must have unique source_id values.")
            source_map[source.source_id] = source

        for item in self.items:
            source = source_map.get(item.source_id)
            if source is None:
                raise ValueError("Every transport item must reference a result source.")
            if item.evidence_state is not source.evidence_state:
                raise ValueError(
                    "Transport item evidence_state must match its source evidence_state."
                )

        if self.state is ResultState.DEMO and any(
            source.evidence_state is not EvidenceState.DEMO for source in self.sources
        ):
            raise ValueError("Demo transport results must contain only demo sources.")
        return self


class FareResult(_TransportResult[FareOffer]):
    pass


class RouteResult(_TransportResult[RouteOption]):
    pass
