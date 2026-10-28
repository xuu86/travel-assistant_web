from __future__ import annotations

import math
from datetime import date, datetime
from typing import ClassVar, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.core.cities import get_city
from app.core.contracts import (
    ContractModel,
    Coverage,
    EvidenceState,
    ResultEnvelope,
    ResultState,
    SourceRef,
)
from app.core.time import normalize_utc

MAX_WEATHER_DAYS = 16
WEATHER_VALUE_FIELDS = (
    "weather_code",
    "temperature_max_c",
    "temperature_min_c",
    "precipitation_probability_max_pct",
    "precipitation_sum_mm",
    "wind_speed_10m_max_kmh",
)

_WMO_LABELS: dict[int, str] = {
    0: "晴",
    1: "大部晴朗",
    2: "局部多云",
    3: "阴",
    45: "雾",
    48: "雾凇",
    51: "小毛毛雨",
    53: "毛毛雨",
    55: "强毛毛雨",
    56: "冻毛毛雨",
    57: "强冻毛毛雨",
    61: "小雨",
    63: "中雨",
    65: "大雨",
    66: "冻雨",
    67: "强冻雨",
    71: "小雪",
    73: "中雪",
    75: "大雪",
    77: "雪粒",
    80: "小阵雨",
    81: "中阵雨",
    82: "强阵雨",
    85: "小阵雪",
    86: "强阵雪",
    95: "雷暴",
    96: "雷暴伴小冰雹",
    99: "雷暴伴大冰雹",
}


class WeatherQuery(ContractModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    city_id: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9-]*$")
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_query(self) -> WeatherQuery:
        if get_city(self.city_id) is None:
            raise ValueError("city_id must refer to a registered city.")
        if self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date.")
        if self.days > MAX_WEATHER_DAYS:
            raise ValueError(f"Weather query cannot exceed {MAX_WEATHER_DAYS} local days.")
        return self

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1

    @property
    def date_range(self) -> tuple[date, date]:
        return self.start_date, self.end_date


class WeatherDay(ContractModel):
    date: date
    weather_code: int | None = Field(default=None, ge=0)
    temperature_max_c: float | None = None
    temperature_min_c: float | None = None
    precipitation_probability_max_pct: float | None = Field(default=None, ge=0, le=100)
    precipitation_sum_mm: float | None = Field(default=None, ge=0)
    wind_speed_10m_max_kmh: float | None = Field(default=None, ge=0)
    missing_fields: list[str] = Field(default_factory=list)

    _numeric_fields: ClassVar[tuple[str, ...]] = (
        "temperature_max_c",
        "temperature_min_c",
        "precipitation_probability_max_pct",
        "precipitation_sum_mm",
        "wind_speed_10m_max_kmh",
    )

    @model_validator(mode="before")
    @classmethod
    def populate_missing_fields(cls, value: object) -> object:
        if not isinstance(value, dict) or "missing_fields" in value:
            return value
        data = dict(value)
        data["missing_fields"] = [
            field_name for field_name in WEATHER_VALUE_FIELDS if data.get(field_name) is None
        ]
        return data

    @field_validator(
        "temperature_max_c",
        "temperature_min_c",
        "precipitation_probability_max_pct",
        "precipitation_sum_mm",
        "wind_speed_10m_max_kmh",
    )
    @classmethod
    def reject_non_finite_numbers(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("Weather numeric values must be finite.")
        return value

    @model_validator(mode="after")
    def validate_day(self) -> WeatherDay:
        missing = set(self.missing_fields)
        if len(missing) != len(self.missing_fields):
            raise ValueError("missing_fields must not contain duplicates.")
        unknown_fields = missing.difference(WEATHER_VALUE_FIELDS)
        if unknown_fields:
            raise ValueError("missing_fields contains an unknown weather field.")
        null_fields = {
            field_name for field_name in WEATHER_VALUE_FIELDS if getattr(self, field_name) is None
        }
        if missing != null_fields:
            raise ValueError("missing_fields must exactly describe null weather fields.")
        if len(null_fields) == len(WEATHER_VALUE_FIELDS):
            raise ValueError("A weather day must contain at least one non-null metric.")
        if (
            self.temperature_max_c is not None
            and self.temperature_min_c is not None
            and self.temperature_max_c < self.temperature_min_c
        ):
            raise ValueError("temperature_max_c must not be below temperature_min_c.")
        return self

    @property
    def weather_code_label(self) -> str:
        if self.weather_code is None:
            return "天气现象待识别"
        return _WMO_LABELS.get(self.weather_code, "天气现象待识别")


class WeatherLocationMetadata(ContractModel):
    city_id: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9-]*$")
    requested_latitude: float = Field(ge=-90, le=90)
    requested_longitude: float = Field(ge=-180, le=180)
    coordinate_system: Literal["WGS84"] = "WGS84"
    resolved_latitude: float | None = Field(default=None, ge=-90, le=90)
    resolved_longitude: float | None = Field(default=None, ge=-180, le=180)
    elevation_m: float | None = Field(default=None, ge=-500, le=10000)

    @field_validator(
        "requested_latitude",
        "requested_longitude",
        "resolved_latitude",
        "resolved_longitude",
        "elevation_m",
    )
    @classmethod
    def reject_non_finite_coordinates(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("Location values must be finite.")
        return value


class ProviderForecastPayload(ContractModel):
    provider_id: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._:-]*$")
    state: Literal[ResultState.LIVE, ResultState.DEMO]
    retrieved_at: datetime
    source: SourceRef
    location: WeatherLocationMetadata
    days: list[WeatherDay] = Field(min_length=1)

    @field_validator("retrieved_at")
    @classmethod
    def normalize_retrieved_at(cls, value: datetime) -> datetime:
        return normalize_utc(value)

    @model_validator(mode="after")
    def validate_source_state(self) -> ProviderForecastPayload:
        if self.state is ResultState.DEMO and self.source.evidence_state is not EvidenceState.DEMO:
            raise ValueError("Demo payloads must carry a demo source state.")
        if self.state is ResultState.LIVE and self.source.evidence_state is EvidenceState.DEMO:
            raise ValueError("Live payloads must not carry a demo source state.")
        dates = [day.date for day in self.days]
        if len(set(dates)) != len(dates):
            raise ValueError("Provider payload must not contain duplicate dates.")
        return self


class WeatherResult(ResultEnvelope[WeatherDay]):
    location: WeatherLocationMetadata
    coverage: Coverage | None = None



