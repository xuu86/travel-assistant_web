from __future__ import annotations

from app.core.contracts import EvidenceState
from app.modules.budget.contracts import BudgetSnapshot
from app.modules.budget.service import calculate_budget


def item(
    cost_id: str,
    *,
    paid: int | None = 0,
    unpaid: int | None = 0,
    completeness: str = "complete",
) -> dict[str, object]:
    return {
        "cost_id": cost_id,
        "category": "其他",
        "reservation_id": None,
        "paid_fen": paid,
        "unpaid_estimate_fen": unpaid,
        "evidence_state": EvidenceState.USER_PROVIDED,
        "completeness": completeness,
    }


def calculate(**overrides: object):
    data: dict[str, object] = {
        "trip_id": "trip-1",
        "total_budget_fen": 600000,
        "reserve_fen": 60000,
        "cost_items": [item("cost-1", paid=200000, unpaid=300000)],
    }
    data.update(overrides)
    return calculate_budget(BudgetSnapshot.model_validate(data))


def test_calculates_paid_unpaid_remaining_and_expected_balance_separately() -> None:
    result = calculate()

    assert result.paid_total_fen == 200000
    assert result.known_unpaid_total_fen == 300000
    assert result.remaining_to_allocate_fen == 400000
    assert result.expected_balance_fen == 40000
    assert result.budget_state == "within_budget"


def test_null_amounts_are_not_treated_as_zero_and_prevent_definite_balance() -> None:
    result = calculate(
        cost_items=[item("cost-1", paid=100000, unpaid=None, completeness="needs_review")]
    )

    assert result.paid_total_fen == 100000
    assert result.known_unpaid_total_fen == 0
    assert result.expected_balance_fen is None
    assert result.budget_state == "needs_review"


def test_known_overspend_is_reported_as_minimum_even_if_other_cost_is_unknown() -> None:
    result = calculate(
        cost_items=[
            item("known", paid=700000, unpaid=0),
            item("unknown", paid=None, unpaid=None, completeness="needs_review"),
        ]
    )

    assert result.budget_state == "over_budget"
    assert result.completeness == "needs_review"
    assert result.minimum_over_budget_fen == 160000
    assert result.expected_balance_fen is None


def test_reserve_reminder_only_at_threshold_when_unset() -> None:
    below = calculate(total_budget_fen=299999, reserve_fen=None)
    threshold = calculate(total_budget_fen=300000, reserve_fen=None)
    explicitly_zero = calculate(total_budget_fen=300000, reserve_fen=0)

    assert not below.reserve_reminder
    assert threshold.reserve_reminder
    assert not explicitly_zero.reserve_reminder


def test_unconfigured_budget_never_claims_within_budget() -> None:
    result = calculate(total_budget_fen=None)

    assert result.budget_state == "unconfigured"
    assert result.remaining_to_allocate_fen is None
    assert result.expected_balance_fen is None


def test_empty_cost_list_needs_review_instead_of_implying_zero_costs() -> None:
    result = calculate(cost_items=[])

    assert result.budget_state == "needs_review"
    assert result.completeness == "needs_review"
    assert result.expected_balance_fen is None


def test_unverified_or_demo_amounts_do_not_claim_definite_budget_status() -> None:
    for evidence_state in (EvidenceState.UNKNOWN, EvidenceState.UNVERIFIED, EvidenceState.DEMO):
        result = calculate(
            cost_items=[
                {
                    **item("cost-1", paid=10000, unpaid=10000),
                    "evidence_state": evidence_state,
                }
            ]
        )

        assert result.budget_state == "needs_review"
        assert result.expected_balance_fen is None
