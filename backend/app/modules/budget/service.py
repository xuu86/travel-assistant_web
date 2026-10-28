from __future__ import annotations

from uuid import UUID

from app.core.contracts import EvidenceState
from app.modules.budget.contracts import BudgetSnapshot, BudgetSummary

RESERVE_REMINDER_THRESHOLD_FEN = 300_000


def calculate_budget(snapshot: BudgetSnapshot, *, request_id: UUID | None = None) -> BudgetSummary:
    paid_known = [item.paid_fen for item in snapshot.cost_items if item.paid_fen is not None]
    unpaid_known = [
        item.unpaid_estimate_fen
        for item in snapshot.cost_items
        if item.unpaid_estimate_fen is not None
    ]
    paid_complete = len(paid_known) == len(snapshot.cost_items)
    paid_total = sum(paid_known) if paid_complete else None
    known_unpaid_total = sum(unpaid_known)

    has_incomplete_cost = not snapshot.cost_items or any(
        item.completeness != "complete"
        or item.paid_fen is None
        or item.unpaid_estimate_fen is None
        or item.evidence_state
        in {EvidenceState.UNVERIFIED, EvidenceState.UNKNOWN, EvidenceState.DEMO}
        for item in snapshot.cost_items
    )
    completeness = "needs_review" if has_incomplete_cost else "complete"
    expected_balance: int | None = None
    remaining: int | None = None
    minimum_over_budget: int | None = None

    if snapshot.total_budget_fen is not None:
        if paid_total is not None:
            remaining = snapshot.total_budget_fen - paid_total

        known_spend = sum(paid_known) + known_unpaid_total + (snapshot.reserve_fen or 0)
        if known_spend > snapshot.total_budget_fen:
            minimum_over_budget = known_spend - snapshot.total_budget_fen

        if not has_incomplete_cost and paid_total is not None:
            expected_balance = (
                snapshot.total_budget_fen
                - paid_total
                - known_unpaid_total
                - (snapshot.reserve_fen or 0)
            )

    if snapshot.total_budget_fen is None:
        budget_state = "unconfigured"
    elif minimum_over_budget is not None:
        budget_state = "over_budget"
    elif has_incomplete_cost:
        budget_state = "needs_review"
    elif expected_balance is not None and expected_balance < 0:
        budget_state = "over_budget"
    else:
        budget_state = "within_budget"

    return BudgetSummary(
        trip_id=snapshot.trip_id,
        total_budget_fen=snapshot.total_budget_fen,
        paid_total_fen=paid_total,
        known_unpaid_total_fen=known_unpaid_total,
        remaining_to_allocate_fen=remaining,
        expected_balance_fen=expected_balance,
        minimum_over_budget_fen=minimum_over_budget,
        budget_state=budget_state,
        completeness=completeness,
        reserve_fen=snapshot.reserve_fen,
        reserve_reminder=(
            snapshot.total_budget_fen is not None
            and snapshot.total_budget_fen >= RESERVE_REMINDER_THRESHOLD_FEN
            and snapshot.reserve_fen is None
        ),
        request_id=request_id or UUID(int=0),
    )
