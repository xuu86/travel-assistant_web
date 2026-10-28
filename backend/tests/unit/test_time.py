from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from app.core.time import (
    SHANGHAI_TZ,
    business_today,
    normalize_utc,
    parse_aware_datetime,
    parse_business_date,
    utc_now,
)


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


def test_business_today_uses_shanghai_timezone_across_utc_date_boundary() -> None:
    before_midnight = FixedClock(datetime(2026, 10, 27, 15, 59, tzinfo=UTC))
    after_midnight = FixedClock(datetime(2026, 10, 27, 16, 0, tzinfo=UTC))

    assert business_today(before_midnight) == date(2026, 10, 27)
    assert business_today(after_midnight) == date(2026, 10, 28)


def test_business_today_does_not_use_host_local_timezone() -> None:
    clock = FixedClock(datetime(2026, 10, 27, 20, 0, tzinfo=timezone(timedelta(hours=-7))))

    assert business_today(clock) == date(2026, 10, 28)


def test_normalize_utc_converts_offset_timestamp() -> None:
    value = datetime(2026, 10, 27, 18, 0, tzinfo=timezone(timedelta(hours=8)))

    assert normalize_utc(value) == datetime(2026, 10, 27, 10, 0, tzinfo=UTC)


@pytest.mark.parametrize("value", [datetime(2026, 10, 27, 10, 0), "2026-10-27T10:00:00"])
def test_naive_datetime_is_rejected(value: datetime | str) -> None:
    with pytest.raises(ValueError, match="timezone"):
        if isinstance(value, str):
            parse_aware_datetime(value)
        else:
            normalize_utc(value)


def test_parse_aware_datetime_accepts_rfc3339_utc_suffix() -> None:
    assert parse_aware_datetime("2026-10-27T10:00:00Z") == datetime(
        2026, 10, 27, 10, 0, tzinfo=UTC
    )


def test_date_only_value_remains_a_business_date() -> None:
    requested_date = date(2028, 2, 29)

    assert parse_business_date("2028-02-29") == requested_date
    assert requested_date.isoformat() == "2028-02-29"
    assert business_today(FixedClock(datetime(2028, 2, 28, 16, 0, tzinfo=UTC))) == requested_date
    assert SHANGHAI_TZ.key == "Asia/Shanghai"


def test_date_only_parser_does_not_accept_a_datetime() -> None:
    with pytest.raises(TypeError, match="date-only"):
        parse_business_date(datetime(2028, 2, 29, 0, 0, tzinfo=UTC))


def test_utc_now_uses_injected_clock() -> None:
    fixed_clock = FixedClock(datetime(2026, 10, 27, 18, 0, tzinfo=timezone(timedelta(hours=8))))

    assert utc_now(fixed_clock) == datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
