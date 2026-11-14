from datetime import date

import pytest

from app.domain.billing import make_line
from app.domain.ledger import (
    balance,
    entry_for_line,
    entry_for_payment,
    entry_for_refund,
    identity_balance,
    summarise,
)
from app.domain.status import invoice_status, is_allowed, payment_status

from .conftest import rs

INV = "INV-STU-000001-2026-000001"
D = date(2026, 8, 10)


def worked_example():
    """Fees 100,000; waiver 10,000; scholarship 30,000; late fee 2,000; payments 40,000 + 30,000; refund 5,000."""
    lines = [make_line(INV, 1, "FEE", rs(100_000), D, "f"),
             make_line(INV, 2, "WAIVER", -rs(10_000), D, "w", applies_to=f"{INV}-L01"),
             make_line(INV, 3, "SCHOLARSHIP", -rs(30_000), D, "s", applies_to=f"{INV}-L01"),
             make_line(INV, 4, "LATE_FEE", rs(2_000), D, "l")]
    pays = [{"payment_id": "PAY-2026-000001", "student_id": "S", "amount_paise": rs(40_000), "received_on": D},
            {"payment_id": "PAY-2026-000002", "student_id": "S", "amount_paise": rs(30_000), "received_on": D}]
    refund = {"refund_id": "REF-2026-000001", "student_id": "S", "amount_paise": rs(5_000), "approved_on": D}
    entries = ([entry_for_line("S", ln) for ln in lines] + [entry_for_payment(p) for p in pays]
               + [entry_for_refund(refund)])
    return lines, pays, refund, entries


def test_balance_of_the_worked_example():
    # 100,000 - 10,000 - 30,000 + 2,000 - 40,000 - 30,000 + 5,000 = -3,000 (the school holds credit)
    assert balance(worked_example()[3]) == -rs(3_000)


def test_summary_splits_the_balance_into_the_stated_figures():
    s = summarise(worked_example()[3])
    assert s == {"charged_paise": rs(102_000), "credits_paise": -rs(40_000), "paid_paise": -rs(70_000),
                 "refunded_paise": rs(5_000), "balance_paise": -rs(3_000)}


def test_three_routes_reach_the_same_balance():
    lines, pays, refund, entries = worked_example()
    total = sum(ln["amount_paise"] for ln in lines)
    assert identity_balance([total], [p["amount_paise"] for p in pays], [refund["amount_paise"]]) \
        == balance(entries) == -rs(3_000)


def test_entry_types_and_signs():
    lines, _, _, entries = worked_example()
    assert [e["entry_type"] for e in entries] == \
        ["CHARGE", "WAIVER", "SCHOLARSHIP", "LATE_FEE", "PAYMENT", "PAYMENT", "REFUND"]
    assert [e["amount_paise"] > 0 for e in entries] == [True, False, False, True, False, False, True]
    assert entries[0]["source_type"] == "invoice_line" and entries[0]["source_id"] == f"{INV}-L01"


@pytest.mark.parametrize("voided, cancelled, outstanding, allocated, as_of, expected", [
    (True, True, 0, 0, date(2026, 10, 22), "VOID"),
    (False, True, 0, 0, date(2026, 10, 22), "CANCELLED"),
    (False, False, 0, 500, date(2026, 10, 22), "PAID"),
    (False, False, 100, 0, date(2026, 9, 10), "OVERDUE"),      # due 2026-09-09, as of the next day
    (False, False, 100, 50, date(2026, 9, 10), "OVERDUE"),      # overdue beats partially paid
    (False, False, 100, 50, date(2026, 9, 9), "PARTIALLY_PAID"),  # due date itself is not yet overdue
    (False, False, 100, 0, date(2026, 9, 9), "ISSUED"),
])
def test_invoice_status_precedence(voided, cancelled, outstanding, allocated, as_of, expected):
    assert invoice_status(voided, cancelled, outstanding, allocated, date(2026, 9, 9), as_of) == expected


def test_payment_status():
    assert payment_status(100, 0, 0) == "RECEIVED"
    assert payment_status(100, 60, 0) == "PARTIALLY_ALLOCATED"
    assert payment_status(100, 100, 0) == "ALLOCATED"
    assert payment_status(100, 60, 40) == "ALLOCATED"     # a refund applies the rest of the money
    assert payment_status(100, 0, 30) == "PARTIALLY_ALLOCATED"


@pytest.mark.parametrize("entity, a, b, ok", [
    ("invoice", None, "ISSUED", True), ("invoice", None, "PAID", False),
    ("invoice", "ISSUED", "PAID", True), ("invoice", "ISSUED", "OVERDUE", True),
    ("invoice", "OVERDUE", "PAID", True), ("invoice", "PAID", "CANCELLED", True),
    ("invoice", "PAID", "ISSUED", False), ("invoice", "CANCELLED", "PAID", False),
    ("invoice", "OVERDUE", "PARTIALLY_PAID", False),
    ("enrollment", "ENROLLED", "WITHDRAWN", True), ("enrollment", "WITHDRAWN", "ENROLLED", False),
    ("scholarship", "AWARDED", "REVOKED", True), ("scholarship", "REVOKED", "APPLIED", False),
    ("refund", "APPROVED", "PAID", True), ("refund", "PAID", "APPROVED", False),
    ("payment", "RECEIVED", "ALLOCATED", True), ("exception", "OPEN", "RESOLVED", True),
    ("exception", "RESOLVED", "OPEN", False), ("eligibility", None, "ELIGIBLE", True),
])
def test_lifecycle_transitions(entity, a, b, ok):
    assert is_allowed(entity, a, b) is ok
