from __future__ import annotations

import logging
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import Settings, get_settings
from app.core.contracts import ErrorCode, PublicError
from app.core.errors import ServiceError, to_public_error
from app.core.request_context import RequestContextMiddleware
from app.modules.budget.router import router as budget_router
from app.modules.foundation.router import router as foundation_router
from app.modules.transport.router import router as transport_router
from app.modules.weather.router import router as weather_router

_logger = logging.getLogger("app.errors")


def _request_id(request: Request) -> UUID | None:
    value = getattr(request.state, "request_id", None)
    return value if isinstance(value, UUID) else None


def _error_response(
    request: Request, public_error: PublicError, *, status_code: int
) -> JSONResponse:
    request_id = _request_id(request) or public_error.request_id
    public_error = public_error.model_copy(update={"request_id": request_id})
    headers = {"X-Request-ID": str(request_id)} if request_id is not None else None
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content=public_error.model_dump(mode="json"),
    )


def _public_error_response(
    request: Request,
    *,
    code: ErrorCode,
    status_code: int,
) -> JSONResponse:
    public_error = to_public_error(ServiceError(code), request_id=_request_id(request))
    return _error_response(request, public_error, status_code=status_code)


def create_app(settings: Settings | None = None) -> FastAPI:
    app_settings = settings if settings is not None else get_settings()
    application = FastAPI(title="行旅智能旅游助手 API", version="0.1.0", debug=False)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(app_settings.allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "HEAD", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )
    application.add_middleware(RequestContextMiddleware)
    application.include_router(foundation_router)
    application.include_router(budget_router)
    application.include_router(weather_router)
    application.include_router(transport_router)

    @application.exception_handler(ServiceError)
    async def service_error_handler(request: Request, exc: ServiceError) -> JSONResponse:
        public_error = to_public_error(exc, request_id=_request_id(request))
        status_codes = {
            ErrorCode.UNCONFIGURED: 503,
            ErrorCode.NO_COVERAGE: 404,
            ErrorCode.RATE_LIMITED: 429,
            ErrorCode.PROVIDER_UNAVAILABLE: 503,
            ErrorCode.POLICY_UNAVAILABLE: 503,
            ErrorCode.VALIDATION_ERROR: 422,
            ErrorCode.CONFIG_INVALID: 500,
            ErrorCode.NOT_FOUND: 404,
            ErrorCode.FORBIDDEN: 403,
            ErrorCode.INTERNAL_ERROR: 500,
        }
        return _error_response(request, public_error, status_code=status_codes[exc.code])

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return _public_error_response(
            request,
            code=ErrorCode.VALIDATION_ERROR,
            status_code=422,
        )

    @application.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        codes = {
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            422: ErrorCode.VALIDATION_ERROR,
        }
        code = codes.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        status_code = exc.status_code if exc.status_code in codes else 500
        return _public_error_response(request, code=code, status_code=status_code)

    @application.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        _logger.error(
            "unhandled_request_error",
            extra={
                "request_id": str(_request_id(request)) if _request_id(request) else None,
                "route_name": getattr(request.scope.get("route"), "name", "unmatched"),
                "exception_type": type(exc).__name__,
            },
        )
        return _public_error_response(
            request,
            code=ErrorCode.INTERNAL_ERROR,
            status_code=500,
        )

    @application.get("/api/health", tags=["foundation"])
    def health() -> dict[str, str]:
        return {"status": "ok", "version": application.version}

    return application


app = create_app()
