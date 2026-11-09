from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.core.cities import get_city
from app.core.contracts import ContractModel, ResultEnvelope

PlaceCategory = Literal["hotels", "activities", "attractions", "maps"]


class PlaceLocation(ContractModel):
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    coordinate_system: Literal["GCJ02"] = "GCJ02"


class PlaceQuery(ContractModel):
    city_id: str = Field(min_length=2, max_length=80)
    keywords: str = Field(default="", max_length=100)
    page: int = Field(default=1, ge=1, le=100)

    @field_validator("city_id")
    @classmethod
    def registered_city(cls, value: str) -> str:
        if get_city(value) is None:
            raise ValueError("A registered city is required.")
        return value

    @field_validator("keywords")
    @classmethod
    def clean_keywords(cls, value: str) -> str:
        if any(ord(char) < 32 for char in value):
            raise ValueError("Keywords must not contain control characters.")
        return value.strip()


class Place(ContractModel):
    id: str = Field(min_length=1, max_length=160)
    name: str = Field(min_length=1, max_length=240)
    address: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, max_length=300)
    telephone: str | None = Field(default=None, max_length=200)
    location: PlaceLocation | None = None
    source_id: Literal["amap.place"] = "amap.place"


class PlaceResult(ResultEnvelope[Place]):
    city_id: str
    category: PlaceCategory
    page: int
    has_more: bool = False


class StaticMapQuery(ContractModel):
    city_id: str
    location: PlaceLocation | None = None
    zoom: int = Field(default=13, ge=3, le=18)

    _registered_city = field_validator("city_id")(PlaceQuery.registered_city.__func__)
