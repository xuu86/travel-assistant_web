from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.contracts import PublicError
from app.core.time import business_today
from app.modules.weather.contracts import WeatherQuery, WeatherResult
from app.modules.weather.service import WeatherService

router = APIRouter(prefix="/api/weather", tags=["weather"])


def _service(request: Request) -> WeatherService:
    service = getattr(request.app.state, "weather_service", None)
    if service is None:
        service = WeatherService(None, today=lambda: business_today())
        request.app.state.weather_service = service
    return service


@router.post(
    "/forecast",
    response_model=WeatherResult,
    summary="Get a daily weather forecast",
    responses={
        422: {"model": PublicError},
        500: {"model": PublicError},
    },
)
def forecast(query: WeatherQuery, request: Request) -> WeatherResult:
    request_id = request.state.request_id
    return _service(request).forecast(query, request_id=request_id)
