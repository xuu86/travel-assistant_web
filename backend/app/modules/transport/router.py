from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.contracts import PublicError
from app.modules.transport.contracts import FareQuery, FareResult, RouteQuery, RouteResult
from app.modules.transport.service import TransportService

router = APIRouter(prefix="/api/transport", tags=["transport"])


def _service(request: Request) -> TransportService:
    service = getattr(request.app.state, "transport_service", None)
    if service is None:
        service = TransportService()
        request.app.state.transport_service = service
    return service


@router.post(
    "/fares/search",
    response_model=FareResult,
    summary="Search flight or rail fare offers",
    responses={422: {"model": PublicError}, 500: {"model": PublicError}},
)
def search_fares(query: FareQuery, request: Request) -> FareResult:
    return _service(request).search_fares(query, request_id=request.state.request_id)


@router.post(
    "/routes/search",
    response_model=RouteResult,
    summary="Search a single local route mode",
    responses={422: {"model": PublicError}, 500: {"model": PublicError}},
)
def search_route(query: RouteQuery, request: Request) -> RouteResult:
    return _service(request).search_route(query, request_id=request.state.request_id)
