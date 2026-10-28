from datetime import UTC, date, datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.contracts import (
    Coverage,
    DateRange,
    EvidenceState,
    MoneyAmount,
    ResultEnvelope,
    ResultState,
    SourceRef,
)

REQUEST_ID = UUID("9d9b4bcb-07f2-484b-8e42-13692d3c5cab")


@pytest.mark.parametrize(
    "state",
    [
        ResultState.LIVE,
        ResultState.PARTIAL,
        ResultState.EMPTY,
        ResultState.DEMO,
        ResultState.UNCONFIGURED,
        ResultState.NO_COVERAGE,
        ResultState.RATE_LIMITED,
        ResultState.UNAVAILABLE,
        ResultState.POLICY_UNAVAILABLE,
    ],
)
def test_public_result_states_remain_distinguishable(state: ResultState) -> None:
    items = ["live data"] if state is ResultState.LIVE else []
    result = ResultEnvelope[str](state=state, items=items, request_id=REQUEST_ID)

    assert result.state is state
    assert result.items == items


def test_result_timestamp_is_aware_and_normalized_to_utc() -> None:
    result = ResultEnvelope[str](
        state=ResultState.LIVE,
        items=["live data"],
        request_id=REQUEST_ID,
        queried_at=datetime(2026, 10, 27, 18, 0, tzinfo=timezone(timedelta(hours=8))),
    )

    assert result.queried_at == datetime(2026, 10, 27, 10, 0, tzinfo=UTC)


def test_result_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        ResultEnvelope[str](
            state=ResultState.LIVE,
            items=["live data"],
            request_id=REQUEST_ID,
            queried_at=datetime(2026, 10, 27, 10, 0),
        )


def test_empty_result_cannot_contain_items() -> None:
    with pytest.raises(ValidationError):
        ResultEnvelope[str](
            state=ResultState.EMPTY,
            items=["a result"],
            request_id=REQUEST_ID,
        )


def test_date_ranges_reject_reversed_bounds() -> None:
    with pytest.raises(ValidationError):
        DateRange(start=date(2026, 10, 28), end=date(2026, 10, 27))


def test_coverage_keeps_requested_and_missing_dates_explicit() -> None:
    coverage = Coverage(
        requested=DateRange(start=date(2026, 10, 27), end=date(2026, 10, 29)),
        covered=[DateRange(start=date(2026, 10, 27), end=date(2026, 10, 28))],
        missing=[DateRange(start=date(2026, 10, 29), end=date(2026, 10, 29))],
    )

    assert coverage.requested.start == date(2026, 10, 27)
    assert coverage.missing[0].start == date(2026, 10, 29)


def test_money_distinguishes_unknown_from_explicit_zero() -> None:
    unknown = MoneyAmount(amount_fen=None)
    zero = MoneyAmount(amount_fen=0)

    assert unknown.amount_fen is None
    assert zero.amount_fen == 0


@pytest.mark.parametrize("invalid_amount", [-1, 1.25, True, "100"])
def test_money_rejects_negative_fractional_or_coercible_values(invalid_amount: object) -> None:
    with pytest.raises(ValidationError):
        MoneyAmount(amount_fen=invalid_amount)


def test_source_ref_keeps_evidence_state_and_sanitized_public_url() -> None:
    source = SourceRef(
        source_id="weather.provider",
        display_name="Weather Source",
        url="https://example.com/forecast?token=must-not-leak#private-fragment",
        retrieved_at=datetime(2026, 10, 27, 10, 0, tzinfo=UTC),
        evidence_state=EvidenceState.VERIFIED,
    )

    assert source.url is not None
    assert source.url.query is None
    assert source.url.fragment is None
    assert source.evidence_state is EvidenceState.VERIFIED


def test_source_ref_rejects_credentials_in_public_url() -> None:
    with pytest.raises(ValidationError):
        SourceRef(
            source_id="weather.provider",
            display_name="Weather Source",
            url="https://" + "user" + ":" + "secret" + "@example.com/forecast",
            retrieved_at=datetime(2026, 10, 27, 10, 0, tzinfo=UTC),
        )


