from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Protocol
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class Clock(Protocol):
    def now(self) -> datetime: ...


def normalize_utc(value: datetime) -> datetime:
    """Normalize a timezone-aware datetime to UTC; reject ambiguous naive values."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Datetime must include a timezone.")
    return value.astimezone(UTC)


def parse_aware_datetime(value: datetime | str) -> datetime:
    """Parse an ISO-8601/RFC-3339 datetime and normalize it to UTC."""
    if isinstance(value, str):
        candidate = value.strip()
        if candidate.endswith(("Z", "z")):
            candidate = f"{candidate[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(candidate)
        except ValueError as exc:
            raise ValueError("Datetime must be a valid ISO-8601 value.") from exc
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise TypeError("Expected an ISO-8601 string or datetime.")
    return normalize_utc(parsed)


def parse_business_date(value: date | str) -> date:
    """Parse a calendar date without attaching a time or timezone."""
    if isinstance(value, datetime):
        raise TypeError("A datetime is not a date-only business value.")
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise TypeError("Expected an ISO-8601 date string or date.")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("Business date must use YYYY-MM-DD.") from exc


def utc_now(clock: Clock | None = None) -> datetime:
    current = clock.now() if clock is not None else datetime.now(UTC)
    return normalize_utc(current)


def business_today(clock: Clock | None = None) -> date:
    """Return today's date according to Asia/Shanghai, independent of host TZ."""
    return utc_now(clock).astimezone(SHANGHAI_TZ).date()
