from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from app.core.contracts import ContractModel, EvidenceState, SourceRef


class CityCenter(ContractModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    coordinate_system: Literal["WGS84"] = "WGS84"
    evidence_state: EvidenceState
    verified_at: datetime
    verification_basis: str = Field(min_length=1, max_length=300)
    feature_designation: Literal["PPLA", "PPLA2"]
    source_record_id: str = Field(min_length=1, max_length=80)
    sources: list[SourceRef] = Field(min_length=1)

    @classmethod
    def official_gazetteer_point(
        cls,
        *,
        latitude: float,
        longitude: float,
        ufi: int,
        feature_designation: Literal["PPLA", "PPLA2"],
    ) -> CityCenter:
        retrieved_at = datetime(2026, 10, 27, 5, 57, 21, tzinfo=UTC)
        return cls(
            latitude=latitude,
            longitude=longitude,
            coordinate_system="WGS84",
            evidence_state=EvidenceState.VERIFIED,
            verified_at=retrieved_at,
            verification_basis=(
                "NGA GeoNames populated-place record classified as an administrative seat; "
                "used as a map anchor, not an administrative-boundary centroid."
            ),
            feature_designation=feature_designation,
            source_record_id=f"UFI:{ufi}",
            sources=[
                SourceRef(
                    source_id=f"nga.geonames.ufi.{ufi}",
                    display_name="NGA GeoNames populated-place record",
                    url="https://geonames.nga.mil/geon-ags/rest/services/RESEARCH/GIS_OUTPUT/MapServer",
                    retrieved_at=retrieved_at,
                    evidence_state=EvidenceState.VERIFIED,
                    attribution="NGA GeoNames; coordinate record queried 2026-10-27.",
                )
            ],
        )


class CityRecord(ContractModel):
    id: str = Field(min_length=2, max_length=80, pattern=r"^[a-z][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=100)
    province: str = Field(min_length=1, max_length=80)
    center: CityCenter
    is_pilot: bool


_CITY_REGISTRY: tuple[CityRecord, ...] = (
    CityRecord(
        id="shanghai",
        name="上海",
        province="上海市",
        center=CityCenter.official_gazetteer_point(
            latitude=31.222222,
            longitude=121.458056,
            ufi=-1924465,
            feature_designation="PPLA",
        ),
        is_pilot=True,
    ),
    CityRecord(
        id="suzhou",
        name="苏州",
        province="江苏省",
        center=CityCenter.official_gazetteer_point(
            latitude=31.304077,
            longitude=120.595380,
            ufi=79514,
            feature_designation="PPLA2",
        ),
        is_pilot=True,
    ),
    CityRecord(
        id="wuxi",
        name="无锡",
        province="江苏省",
        center=CityCenter.official_gazetteer_point(
            latitude=31.568873,
            longitude=120.288573,
            ufi=-1931162,
            feature_designation="PPLA2",
        ),
        is_pilot=True,
    ),
    CityRecord(
        id="jiaxing",
        name="嘉兴",
        province="浙江省",
        center=CityCenter.official_gazetteer_point(
            latitude=30.752198,
            longitude=120.749997,
            ufi=-1912033,
            feature_designation="PPLA2",
        ),
        is_pilot=True,
    ),
    CityRecord(
        id="hangzhou",
        name="杭州",
        province="浙江省",
        center=CityCenter.official_gazetteer_point(
            latitude=30.293650,
            longitude=120.161419,
            ufi=-1908366,
            feature_designation="PPLA",
        ),
        is_pilot=True,
    ),
)


def get_cities() -> list[CityRecord]:
    """Return detached copies so callers cannot mutate the shared registry."""
    return [city.model_copy(deep=True) for city in _CITY_REGISTRY]


def get_city(city_id: str) -> CityRecord | None:
    """Return a detached record for a stable city ID, if registered."""
    for city in _CITY_REGISTRY:
        if city.id == city_id:
            return city.model_copy(deep=True)
    return None
