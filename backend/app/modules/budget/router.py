from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.contracts import PublicError
from app.modules.budget.contracts import BudgetSnapshot, BudgetSummary
from app.modules.budget.service import calculate_budget

router = APIRouter(prefix="/api/budget", tags=["budget"])


@router.post(
    "/calculate",
    response_model=BudgetSummary,
    summary="Calculate a travel budget snapshot",
    responses={422: {"model": PublicError}, 500: {"model": PublicError}},
)
def calculate(snapshot: BudgetSnapshot, request: Request) -> BudgetSummary:
    return calculate_budget(snapshot, request_id=request.state.request_id)
