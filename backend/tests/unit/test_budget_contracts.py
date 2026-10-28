from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.contracts import EvidenceState
from app.modules.budget.contracts import BudgetSnapshot, CostItem


def cost(**overrides: object) -> dict[str, object]:
    item: dict[str, object] = {
        "cost_id": "cost-1",
        "category": "住宿",
        "reservation_id": None,
        "paid_fen": 0,
        "unpaid_estimate_fen": 12000,
        "evidence_state": EvidenceState.USER_PROVIDED,
        "completeness": "complete",
    }
    item.update(overrides)
    return item


def test_snapshot_preserves_null_and_zero_as_distinct_values() -> None:
    snapshot = BudgetSnapshot.model_validate(
        {
            "trip_id": "trip-1",
            "total_budget_fen": None,
            "reserve_fen": 0,
            "cost_items": [cost(paid_fen=None, unpaid_estimate_fen=0, completeness="needs_review")],
        }
    )

    assert snapshot.total_budget_fen is None
    assert snapshot.reserve_fen == 0
    assert snapshot.cost_items[0].paid_fen is None
    assert snapshot.cost_items[0].unpaid_estimate_fen == 0


@pytest.mark.parametrize("amount", [-1, 1.5, True])
def test_cost_rejects_negative_float_and_boolean_amounts(amount: object) -> None:
    with pytest.raises(ValidationError):
        CostItem.model_validate(cost(paid_fen=amount, completeness="needs_review"))


def test_complete_cost_requires_known_payment_amounts() -> None:
    with pytest.raises(ValidationError):
        CostItem.model_validate(cost(paid_fen=None))


def test_snapshot_rejects_duplicate_cost_ids() -> None:
    with pytest.raises(ValidationError, match="cost_id"):
        BudgetSnapshot.model_validate(
            {"trip_id": "trip-1", "cost_items": [cost(), cost(unpaid_estimate_fen=8000)]}
        )


def test_snapshot_rejects_multiple_primary_costs_for_one_reservation() -> None:
    with pytest.raises(ValidationError, match="reservation"):
        BudgetSnapshot.model_validate(
            {
                "trip_id": "trip-1",
                "cost_items": [
                    cost(cost_id="cost-1", reservation_id="reservation-1"),
                    cost(cost_id="cost-2", reservation_id="reservation-1"),
                ],
            }
        )


def test_unknown_category_and_evidence_state_are_rejected() -> None:
    with pytest.raises(ValidationError):
        CostItem.model_validate(cost(category="航空公司"))
    with pytest.raises(ValidationError):
        CostItem.model_validate(cost(evidence_state="platform_quote"))
