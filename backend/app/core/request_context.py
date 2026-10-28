from __future__ import annotations

import logging
import time
from contextvars import ContextVar, Token
from typing import Any
from uuid import UUID, uuid4

from starlette.datastructures import MutableHeaders

request_id_var: ContextVar[UUID | None] = ContextVar("request_id", default=None)
_request_logger = logging.getLogger("app.request")


def current_request_id() -> UUID | None:
    return request_id_var.get()


class RequestContextMiddleware:
    """Attach a fresh request ID and emit metadata-only completion logs."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid4()
        request_id_text = str(request_id)
        scope.setdefault("state", {})["request_id"] = request_id
        token: Token[UUID | None] = request_id_var.set(request_id)
        started_at = time.perf_counter()
        status_code = 500

        async def send_with_request_id(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = MutableHeaders(scope=message)
                headers["X-Request-ID"] = request_id_text
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            route = scope.get("route")
            route_name = getattr(route, "name", "unmatched")
            _request_logger.info(
                "request_complete",
                extra={
                    "request_id": request_id_text,
                    "route_name": route_name,
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started_at) * 1000, 2),
                },
            )
            request_id_var.reset(token)
