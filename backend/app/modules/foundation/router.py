from fastapi import APIRouter, HTTPException

from app.core.cities import CityRecord, get_cities, get_city
from app.core.contracts import PublicError

router = APIRouter(prefix="/api/foundation", tags=["foundation"])


@router.get(
    "/cities",
    response_model=list[CityRecord],
    summary="List registered cities",
    responses={422: {"model": PublicError}},
)
def list_cities() -> list[CityRecord]:
    """Return the local city registry; this does not imply provider coverage."""
    return get_cities()


@router.get(
    "/cities/{city_id}",
    response_model=CityRecord,
    summary="Get a registered city",
    responses={404: {"model": PublicError}, 422: {"model": PublicError}},
)
def read_city(city_id: str) -> CityRecord:
    city = get_city(city_id)
    if city is None:
        raise HTTPException(status_code=404)
    return city
