"""Time helpers."""

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    """Return the current UTC timestamp."""

    return datetime.now(tz=timezone.utc)


def local_now(timezone_name: str) -> datetime:
    """Return the current timestamp in the configured timezone."""

    return datetime.now(tz=ZoneInfo(timezone_name))


def current_local_date(timezone_name: str) -> date:
    """Return the current local date for a timezone."""

    return local_now(timezone_name).date()
