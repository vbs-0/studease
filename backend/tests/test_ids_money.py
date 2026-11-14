from app import ids
from app.money import clamp, inr, pct


def test_pct_exact_two_percent():
    assert pct(100_000_00, 200) == 2_000_00


def test_pct_rounds_half_up():
    assert pct(333, 5000) == 167  # 166.5 -> 167
    assert pct(1, 5000) == 1      # 0.5 -> 1
    assert pct(0, 5000) == 0


def test_pct_negative_is_symmetric():
    assert pct(-333, 5000) == -167


def test_clamp():
    assert clamp(10, 50, 500) == 50
    assert clamp(900, 50, 500) == 500
    assert clamp(100, 50, 500) == 100


def test_inr_indian_grouping():
    assert inr(0) == "₹0.00"
    assert inr(99) == "₹0.99"
    assert inr(1234567) == "₹12,345.67"
    assert inr(123456789) == "₹12,34,567.89"
    assert inr(-50000) == "-₹500.00"


def test_id_examples_from_the_brief():
    assert ids.student_id(1) == "STU-000001"
    assert ids.term_id("FALL") == "TERM-2026-FALL"
    assert ids.invoice_id(1, 1) == "INV-STU-000001-2026-000001"
    assert ids.scholarship_id(1) == "SCH-2026-000001"
    assert ids.payment_id(1) == "PAY-2026-000001"
    assert ids.allocation_id("PAY-2026-000001", 1) == "ALLOC-PAY-2026-000001-01"


def test_every_generated_id_matches_its_pattern():
    inv = ids.invoice_id(42, 7)
    samples = {
        "program": ids.program_id(3), "term": ids.term_id("SPRING"), "scholarship_scheme": "MERIT_GOLD",
        "student": ids.student_id(42),
        "fee_schedule": ids.fee_schedule_id("PRG-01", "FALL", "TUITION", 2),
        "enrollment": ids.enrollment_id(42, "SUMMER"), "invoice": inv,
        "eligibility": ids.eligibility_id(5), "scholarship": ids.scholarship_id(5),
        "invoice_line": ids.invoice_line_id(inv, 3), "payment": ids.payment_id(9),
        "payment_allocation": ids.allocation_id(ids.payment_id(9), 2), "refund": ids.refund_id(1),
        "ledger_entry": ids.ledger_id(1), "student_balance": ids.student_id(42),
        "event": ids.event_id(1), "app_user": ids.user_id(1), "exception": ids.exception_id(1),
        "ground_truth": ids.gt_id(1),
    }
    assert set(samples) == set(ids.PATTERNS)
    for table, value in samples.items():
        assert ids.matches(table, value), (table, value)


def test_patterns_reject_malformed_ids():
    assert not ids.matches("student", "STU-1")
    assert not ids.matches("student", "stu-000001")
    assert not ids.matches("invoice", "INV-STU-000001-2026-1")
    assert not ids.matches("student", "STU-000001 ")


def test_student_no_roundtrip():
    assert ids.student_no(ids.student_id(1234)) == 1234
