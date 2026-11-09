from fastapi import APIRouter, Request

from app.core.contracts import PublicError
from app.core.places import PlaceQuery, PlaceResult

router = APIRouter(prefix="/api/attractions", tags=["attractions"])


@router.post("/search", response_model=PlaceResult, responses={422: {"model": PublicError}})
def search(query: PlaceQuery, request: Request) -> PlaceResult:
    return request.app.state.amap_service.search(
        query,
        "attractions",
        request_id=request.state.request_id,
    )
