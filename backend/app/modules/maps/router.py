from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.core.contracts import PublicError
from app.core.places import PlaceQuery, PlaceResult, StaticMapQuery

router = APIRouter(prefix="/api/maps", tags=["maps"])


@router.post("/search", response_model=PlaceResult, responses={422: {"model": PublicError}})
def search(query: PlaceQuery, request: Request) -> PlaceResult:
    return request.app.state.amap_service.search(
        query,
        "maps",
        request_id=request.state.request_id,
    )


@router.post(
    "/static",
    response_class=Response,
    responses={
        200: {"content": {"image/png": {}, "image/jpeg": {}, "image/gif": {}}},
        422: {"model": PublicError},
        503: {"model": PublicError},
    },
)
def static_map(query: StaticMapQuery, request: Request) -> Response:
    body, media_type = request.app.state.amap_service.static_map(query)
    return Response(
        body,
        media_type=media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
