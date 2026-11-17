from __future__ import annotations

import hmac
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request, Response
from fastapi import status as http_status

from app.core.config import Settings
from app.core.contracts import ErrorCode
from app.core.errors import ServiceError
from app.modules.auth.contracts import IdentityResponse, LoginRequest, RegisterRequest
from app.modules.auth.service import SESSION_TTL_SECONDS, AuthService, SessionIdentity

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
COOKIE_NAME = "travel_session"


def _service(request: Request) -> AuthService:
    return request.app.state.auth_service


def _settings(request: Request) -> Settings:
    return request.app.state.settings


AuthServiceDep = Annotated[AuthService, Depends(_service)]
SettingsDep = Annotated[Settings, Depends(_settings)]


def _check_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    host = request.headers.get("host")
    expected = f"{request.url.scheme}://{host}" if host else ""
    if not origin or not hmac.compare_digest(origin, expected):
        raise ServiceError(ErrorCode.FORBIDDEN)
    parsed = urlsplit(origin)
    allowed_local_hosts = {"localhost", "127.0.0.1", "::1"}
    if request.app.state.settings.env == "test":
        allowed_local_hosts.add("testserver")
    if parsed.scheme != "https" and parsed.hostname not in allowed_local_hosts:
        raise ServiceError(ErrorCode.FORBIDDEN)


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.env == "production",
        samesite="lax",
        path="/",
        max_age=SESSION_TTL_SECONDS,
    )


def _account_response(identity: SessionIdentity) -> IdentityResponse:
    return IdentityResponse(
        identity_type="account",
        owner_id=identity.owner_id,
        display_name=identity.display_name,
    )


@router.get("/session", response_model=IdentityResponse)
def get_session(request: Request, service: AuthServiceDep, response: Response) -> IdentityResponse:
    identity = service.identify(request.cookies.get(COOKIE_NAME))
    if identity is None:
        response.delete_cookie(key=COOKIE_NAME, path="/", httponly=True, samesite="lax")
        return IdentityResponse(identity_type="guest")
    return _account_response(identity)


@router.post("/login", response_model=IdentityResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    service: AuthServiceDep,
    settings: SettingsDep,
) -> IdentityResponse:
    _check_same_origin(request)
    if not service.configured:
        raise ServiceError(ErrorCode.UNCONFIGURED)
    client_host = request.client.host if request.client else "unknown"
    token, identity = service.authenticate(payload.username, payload.password, client_host)
    _set_session_cookie(response, token, settings)
    return _account_response(identity)


@router.post("/register", status_code=http_status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request, service: AuthServiceDep) -> dict[str, str]:
    _check_same_origin(request)
    client_host = request.client.host if request.client else "unknown"
    if not service.register(payload.username, payload.password, client_host):
        raise ServiceError(ErrorCode.VALIDATION_ERROR)
    return {"status": "created"}


@router.post("/logout", status_code=http_status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, service: AuthServiceDep) -> Response:
    _check_same_origin(request)
    service.logout(request.cookies.get(COOKIE_NAME))
    response.delete_cookie(key=COOKIE_NAME, path="/", httponly=True, samesite="lax")
    response.status_code = http_status.HTTP_204_NO_CONTENT
    return response
