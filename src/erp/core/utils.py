import calendar
from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def get_start_of_month() -> datetime:
    now = datetime.now(UTC)
    return datetime(now.year, now.month, 1, tzinfo=UTC)


def get_end_of_month() -> datetime:
    now = datetime.now(UTC)
    _, last_day = calendar.monthrange(now.year, now.month)
    return datetime(now.year, now.month, last_day, 23, 59, 59, 999999, tzinfo=UTC)
