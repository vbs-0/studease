from datetime import date

from app.domain.latefees import late_fee, late_fee_date

from .conftest import rs


def test_two_percent_of_a_large_balance():
    assert late_fee(rs(100_000)) == rs(2_000)


def test_small_balance_pays_the_floor():
    assert late_fee(rs(1_000)) == rs(500)        # 2% would be 20
    assert late_fee(rs(25_000)) == rs(500)       # 2% is exactly 500


def test_large_balance_pays_the_cap():
    assert late_fee(rs(250_000)) == rs(5_000)    # 2% is exactly 5,000
    assert late_fee(rs(900_000)) == rs(5_000)


def test_nothing_outstanding_means_no_fee():
    assert late_fee(0) == 0
    assert late_fee(-100) == 0


def test_rounds_half_up_to_the_paise():
    assert late_fee(rs(40_000) + 25) == rs(800) + 1   # 2% of 4,000,025 paise = 80,000.5 -> 80,001


def test_fee_is_posted_eight_days_after_the_due_date():
    assert late_fee_date(date(2026, 9, 9)) == date(2026, 9, 17)
