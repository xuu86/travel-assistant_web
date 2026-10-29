from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.modules.assistant.contracts import AssistantResponse, ChatRequest
from app.modules.assistant.service import AssistantService

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


def _service(request: Request) -> AssistantService:
    service = getattr(request.app.state, "assistant_service", None)
    if service is None:
        service = AssistantService(get_settings())
        request.app.state.assistant_service = service
    return service


@router.post(
    "/chat",
    response_model=AssistantResponse,
    summary="Ask the travel assistant",
)
async def chat(body: ChatRequest, request: Request) -> AssistantResponse:
    return await _service(request).chat(body, request_id=request.state.request_id)
