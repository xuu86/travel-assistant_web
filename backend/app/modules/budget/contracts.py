from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.contracts import ContractModel, EvidenceState

CostCategory = Literal["往返交通", "住宿", "餐饮", "市内交通", "门票", "活动", "其他"]
Completeness = Literal["complete", "needs_review"]
BudgetState = Literal["unconfigured", "needs_review", "within_budget", "over_budget"]


class CostItem(ContractModel):
    cost_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    category: CostCategory
    reservation_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=120,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$",
    )
    paid_fen: int | None = Field(ge=0)
    unpaid_estimate_fen: int | None = Field(ge=0)
    evidence_state: EvidenceState
    completeness: Completeness

    @field_validator("evidence_state", mode="before")
    @classmethod
    def parse_evidence_state(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return EvidenceState(value)
            except ValueError:
                return value
        return value

    @model_validator(mode="after")
    def validate_complete_amounts(self) -> CostItem:
        if self.completeness == "complete" and (
            self.paid_fen is None or self.unpaid_estimate_fen is None
        ):
            raise ValueError("Complete cost items require known paid and unpaid amounts.")
        return self


class BudgetSnapshot(ContractModel):
    trip_id: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    total_budget_fen: int | None = Field(default=None, ge=0)
    reserve_fen: int | None = Field(default=None, ge=0)
    cost_items: list[CostItem]

    @model_validator(mode="after")
    def validate_unique_cost_ownership(self) -> BudgetSnapshot:
        cost_ids = [item.cost_id for item in self.cost_items]
        if len(cost_ids) != len(set(cost_ids)):
            raise ValueError("cost_id values must be unique.")
        reservation_ids = [
            item.reservation_id for item in self.cost_items if item.reservation_id is not None
        ]
        if len(reservation_ids) != len(set(reservation_ids)):
            raise ValueError("Each reservation may map to only one primary cost item.")
        return self


class BudgetSummary(ContractModel):
    trip_id: str
    total_budget_fen: int | None
    paid_total_fen: int | None
    known_unpaid_total_fen: int
    remaining_to_allocate_fen: int | None
    expected_balance_fen: int | None
    minimum_over_budget_fen: int | None
    budget_state: BudgetState
    completeness: Completeness
    reserve_fen: int | None
    reserve_reminder: bool
    request_id: UUID
