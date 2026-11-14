"""Late fees (R-LATE): 2% of what is outstanding after the grace period, floor INR 500, cap INR 5,000."""
from datetime import date, timedelta

from app.domain.calendar import GRACE_DAYS
from app.money import clamp, pct

RATE_BP = 200
MIN_FEE = 500 * 100
MAX_FEE = 5_000 * 100


def late_fee(outstanding: int) -> int:
    """R-LATE-2. Nothing outstanding means no fee."""
    if outstanding <= 0:
        return 0
    return clamp(pct(outstanding, RATE_BP), MIN_FEE, MAX_FEE)


def late_fee_date(due: date) -> date:
    """R-LATE-1: the fee is posted the day after the grace period ends (due date + 8 days)."""
    return due + timedelta(days=GRACE_DAYS + 1)
