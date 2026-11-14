from datetime import date

import pytest

from app.domain.billing import line_net, make_line
from app.domain.calendar import TERMS
from app.domain.withdrawal import (
    adjustment_lines,
    classify,
    excess_by_line,
    plan_reversals,
    refund_due,
    refund_share_bp,
)

from .conftest import rs

FALL = TERMS["FALL"]  # starts 2026-08-17
INV = "INV-STU-000001-2026-000001"


@pytest.mark.parametrize("left_on, status, share", [
    (date(2026, 8, 16), "CANCELLED", 10000),   # the day before the term starts
    (date(2026, 8, 17), "WITHDRAWN", 7500),    # day 0
    (date(2026, 8, 31), "WITHDRAWN", 7500),    # day 14
    (date(2026, 9, 1), "WITHDRAWN", 5000),     # day 15
    (date(2026, 9, 16), "WITHDRAWN", 5000),    # day 30
    (date(2026, 9, 17), "WITHDRAWN", 0),       # day 31
])
def test_band_boundaries(left_on, status, share):
    assert classify(left_on, FALL) == status
    assert refund_share_bp(left_on, FALL) == share


def invoice_lines():
    d = date(2026, 8, 10)
    return [make_line(INV, 1, "FEE", rs(100_000), d, "Tuition fee"),
            make_line(INV, 2, "WAIVER", -rs(10_000), d, "w", applies_to=f"{INV}-L01"),
            make_line(INV, 3, "FEE", rs(5_000), d, "Library fee"),
            make_line(INV, 4, "LATE_FEE", rs(2_000), d, "Late fee")]


def test_adjustment_reverses_the_share_of_net_charges_and_skips_late_fees():
    adj = adjustment_lines(INV, invoice_lines(), 7500, 5, date(2026, 8, 20))
    assert [(a["applies_to_line_id"][-3:], a["amount_paise"]) for a in adj] == \
        [("L01", -rs(67_500)), ("L03", -rs(3_750))]      # 75% of 90,000 and of 5,000
    assert [a["line_no"] for a in adj] == [5, 6]
    assert all(a["line_type"] == "ADJUSTMENT" for a in adj)


def test_full_cancellation_zeroes_every_fee_line():
    lines = invoice_lines()
    lines += adjustment_lines(INV, lines, 10000, 5, date(2026, 8, 1))
    assert line_net(f"{INV}-L01", lines) == 0 and line_net(f"{INV}-L03", lines) == 0
    assert line_net(f"{INV}-L04", lines) == rs(2_000)    # late fee untouched


def test_zero_share_makes_no_adjustment():
    assert adjustment_lines(INV, invoice_lines(), 0, 5, date(2026, 10, 1)) == []


def alloc(aid, pay, line, amount, day):
    return {"allocation_id": aid, "payment_id": pay, "invoice_line_id": line, "amount_paise": amount,
            "allocated_on": date(2026, 9, day)}


def test_excess_is_what_was_paid_above_what_is_now_owed():
    lines = [make_line(INV, 1, "FEE", 100, date(2026, 8, 10), "f"),
             make_line(INV, 2, "ADJUSTMENT", -75, date(2026, 8, 20), "a", applies_to=f"{INV}-L01")]
    assert excess_by_line(lines, [alloc("A1", "P1", f"{INV}-L01", 100, 1)]) == {f"{INV}-L01": 75}
    assert excess_by_line(lines, [alloc("A1", "P1", f"{INV}-L01", 25, 1)]) == {}


def test_reversals_give_back_the_newest_allocation_first():
    line = f"{INV}-L01"
    allocations = [alloc("A1", "P1", line, 60, 1), alloc("A2", "P2", line, 40, 5)]
    assert plan_reversals(allocations, {line: 50}) == [("P2", line, 40), ("P1", line, 10)]


def test_reversals_account_for_earlier_reversals():
    line = f"{INV}-L01"
    allocations = [alloc("A1", "P1", line, 100, 1), alloc("A2", "P1", line, -30, 3)]
    assert plan_reversals(allocations, {line: 90}) == [("P1", line, 70)]


def test_refund_never_exceeds_net_paid():
    assert refund_due(75, 100) == 75
    assert refund_due(75, 40) == 40
    assert refund_due(75, 0) == 0
    assert refund_due(0, 100) == 0
