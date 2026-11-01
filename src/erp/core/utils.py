import calendar
import math
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


def get_dynamic_amount_step(min_val: float, max_val: float) -> float:
    amount_range = max_val - min_val

    if amount_range <= 0:
        amount_range = max(abs(min_val), 1)

    raw_step = amount_range / 20
    magnitude = 10 ** math.floor(math.log10(raw_step))
    normalized = raw_step / magnitude

    if normalized <= 1:
        multiplier = 1
    elif normalized <= 2:
        multiplier = 2
    elif normalized <= 5:
        multiplier = 5
    else:
        multiplier = 10

    return multiplier * magnitude


def get_amount_slider_range(
    min_val: float,
    max_val: float,
) -> tuple[float, float, float]:
    step = get_dynamic_amount_step(min_val, max_val)

    if min_val == max_val:
        padding = max(abs(min_val) * 0.1, step * 2)
        min_val = max(0, min_val - padding)
        max_val = max_val + padding

    clean_min = math.floor(min_val / step) * step
    clean_max = math.ceil(max_val / step) * step

    return round(clean_min, 2), round(clean_max, 2), round(step, 2)
