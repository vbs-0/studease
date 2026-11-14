from datetime import date

import pytest

from app.domain.allocation import allocate, open_lines
from app.domain.billing import make_line


def test_exact_payment_clears_lines_in_order():
    assert allocate(150, [("a", 100), ("b", 50)]) == ([("a", 100), ("b", 50)], 0)


def test_partial_payment_stops_inside_a_line():
    assert allocate(120, [("a", 100), ("b", 50)]) == ([("a", 100), ("b", 20)], 0)
    assert allocate(30, [("a", 100)]) == ([("a", 30)], 0)


def test_overpayment_returns_the_remainder():
    assert allocate(200, [("a", 100), ("b", 50)]) == ([("a", 100), ("b", 50)], 50)


def test_nothing_open_leaves_everything_unapplied():
    assert allocate(30, []) == ([], 30)


def test_lines_with_nothing_owed_are_skipped():
    assert allocate(10, [("a", 0), ("b", -5), ("c", 20)]) == ([("c", 10)], 0)


@pytest.mark.parametrize("amount", [1, 49, 50, 51, 149, 150, 151, 10_000])
def test_allocations_plus_remainder_equal_the_payment(amount):
    allocations, left = allocate(amount, [("a", 100), ("b", 50)])
    assert sum(v for _, v in allocations) + left == amount
    assert all(v <= cap for (lid, v), cap in zip(allocations, (100, 50), strict=False))


def test_open_lines_are_ordered_by_due_date_then_line_number():
    inv_old, inv_new = "INV-STU-000001-2026-000001", "INV-STU-000001-2026-000002"
    invoices = [{"invoice_id": inv_new, "due_date": date(2026, 9, 9)},
                {"invoice_id": inv_old, "due_date": date(2026, 2, 4)}]
    lines = [make_line(inv_new, 1, "FEE", 100, date(2026, 8, 10), "n1"),
             make_line(inv_old, 1, "FEE", 100, date(2026, 1, 5), "o1"),
             make_line(inv_old, 2, "FEE", 100, date(2026, 1, 5), "o2")]
    paid = [{"invoice_line_id": f"{inv_old}-L01", "amount_paise": 100}]
    got = open_lines(invoices, lines, paid)
    assert got == [(f"{inv_old}-L02", 100), (f"{inv_new}-L01", 100)]   # L01 of the old invoice is paid


def test_open_lines_ignore_invoices_that_were_not_passed_in():
    inv = "INV-STU-000001-2026-000001"
    lines = [make_line(inv, 1, "FEE", 100, date(2026, 1, 5), "f")]
    assert open_lines([], lines, []) == []
