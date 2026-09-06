from datetime import UTC, datetime

import pytest
from freezegun import freeze_time

from erp.core.utils import get_end_of_month, get_start_of_month, utc_now


def test_utc_now_returns_correct_time_and_timezone():
    """Verifies utc_now captures the exact frozen instant with explicit UTC metadata."""
    frozen_target = "2026-07-08 20:50:40.123456"

    with freeze_time(frozen_target):
        result = utc_now()

        assert result == datetime(2026, 7, 8, 20, 50, 40, 123456, tzinfo=UTC)
        assert result.tzinfo is UTC


@pytest.mark.parametrize(
    "current_time, expected_start",
    [
        ("2026-07-08 12:00:00", datetime(2026, 7, 1, 0, 0, tzinfo=UTC)),
        ("2026-01-01 00:00:00", datetime(2026, 1, 1, 0, 0, tzinfo=UTC)),
        ("2026-12-31 23:59:59", datetime(2026, 12, 1, 0, 0, tzinfo=UTC)),
    ],
)
def test_get_start_of_month(current_time, expected_start):
    """Verifies that regardless of the day or time, it resets cleanly to midnight on day 1."""
    with freeze_time(current_time):
        assert get_start_of_month() == expected_start


@pytest.mark.parametrize(
    "current_time, expected_end",
    [
        # Standard 31-day month
        ("2026-07-08 12:00:00", datetime(2026, 7, 31, 23, 59, 59, 999999, tzinfo=UTC)),
        # Standard 30-day month
        ("2026-04-15 06:30:00", datetime(2026, 4, 30, 23, 59, 59, 999999, tzinfo=UTC)),
        # Year end transition
        ("2026-12-25 00:00:00", datetime(2026, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)),
    ],
)
def test_get_end_of_month_regular_months(current_time, expected_end):
    """Verifies the calendar limits resolve accurately to the final microsecond of the month."""
    with freeze_time(current_time):
        assert get_end_of_month() == expected_end


def test_get_end_of_month_leap_year_february():
    """Verifies calendar.monthrange handles February 29th correctly on a leap year."""
    leap_year_feb = "2024-02-14 12:00:00"

    with freeze_time(leap_year_feb):
        expected = datetime(2024, 2, 29, 23, 59, 59, 999999, tzinfo=UTC)
        assert get_end_of_month() == expected


def test_get_end_of_month_non_leap_year_february():
    """Verifies calendar.monthrange handles February 28th correctly on a non-leap year."""
    non_leap_year_feb = "2025-02-14 12:00:00"

    with freeze_time(non_leap_year_feb):
        expected = datetime(2025, 2, 28, 23, 59, 59, 999999, tzinfo=UTC)
        assert get_end_of_month() == expected
