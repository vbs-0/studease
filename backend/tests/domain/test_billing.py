from datetime import date

from app.domain.billing import (
    build_invoice_lines,
    eligible_fees,
    invoice_total,
    line_net,
    make_line,
    outstanding_by_line,
)

from .conftest import make_fee, make_student, rs

INV = "INV-STU-000001-2026-000001"
ISSUE = date(2026, 8, 10)
FEES = [make_fee("TUITION", 100_000), make_fee("LAB", 20_000), make_fee("LIBRARY", 5_000),
        make_fee("TECHNOLOGY", 3_000), make_fee("EXAM", 2_000)]


def build(**student_kw):
    return build_invoice_lines(INV, make_student(**student_kw), FEES, ISSUE)


def by_desc(lines, word):
    return next(ln for ln in lines if word in ln["description"])


def test_lines_follow_fee_type_order_and_are_numbered_from_one():
    lines = build()
    assert [ln["line_no"] for ln in lines] == [1, 2, 3, 4, 5]
    assert [ln["line_type"] for ln in lines] == ["FEE"] * 5
    assert lines[0]["invoice_line_id"] == f"{INV}-L01"
    assert lines[0]["description"] == "Tuition fee"


def test_total_is_the_sum_of_lines():
    assert invoice_total(build()) == rs(130_000)


def test_staff_ward_waives_all_tuition():
    lines = build(waiver_type="STAFF_WARD")
    waiver = by_desc(lines, "Waiver")
    assert waiver["line_type"] == "WAIVER" and waiver["amount_paise"] == -rs(100_000)
    assert waiver["applies_to_line_id"] == f"{INV}-L01"
    assert invoice_total(lines) == rs(30_000)


def test_sibling_waives_ten_percent_of_tuition():
    lines = build(waiver_type="SIBLING")
    assert by_desc(lines, "Waiver")["amount_paise"] == -rs(10_000)


def test_hardship_waives_library_technology_and_exam_in_full():
    lines = build(waiver_type="HARDSHIP")
    waivers = [ln for ln in lines if ln["line_type"] == "WAIVER"]
    assert sorted(w["amount_paise"] for w in waivers) == [-rs(5_000), -rs(3_000), -rs(2_000)]
    assert invoice_total(lines) == rs(120_000)


def test_no_waiver_when_target_fee_is_absent():
    lines = build_invoice_lines(INV, make_student(waiver_type="STAFF_WARD"), [make_fee("LAB", 20_000)], ISSUE)
    assert [ln["line_type"] for ln in lines] == ["FEE"]


def test_line_net_subtracts_only_requested_credit_types():
    lines = build(waiver_type="SIBLING")
    tuition = f"{INV}-L01"
    lines.append(make_line(INV, 7, "SCHOLARSHIP", -rs(30_000), ISSUE, "s", applies_to=tuition))
    assert line_net(tuition, lines) == rs(60_000)
    assert line_net(tuition, lines, ("WAIVER",)) == rs(90_000)


def test_outstanding_subtracts_credits_and_allocations():
    lines = build(waiver_type="SIBLING")
    alloc = [{"invoice_line_id": f"{INV}-L01", "amount_paise": rs(40_000)},
             {"invoice_line_id": f"{INV}-L02", "amount_paise": rs(20_000)}]
    out = outstanding_by_line(lines, alloc)
    assert out[f"{INV}-L01"] == rs(50_000)   # 100,000 - 10,000 waiver - 40,000 paid
    assert out[f"{INV}-L02"] == 0            # lab fully paid
    assert out[f"{INV}-L03"] == rs(5_000)
    assert f"{INV}-L06" not in out           # credit lines are not charge lines


def test_outstanding_goes_negative_when_a_paid_line_is_reduced():
    lines = [make_line(INV, 1, "FEE", rs(100), ISSUE, "f"),
             make_line(INV, 2, "ADJUSTMENT", -rs(75), ISSUE, "a", applies_to=f"{INV}-L01")]
    out = outstanding_by_line(lines, [{"invoice_line_id": f"{INV}-L01", "amount_paise": rs(100)}])
    assert out[f"{INV}-L01"] == -rs(75)


def test_eligible_fees_count_tuition_and_lab_net_of_waivers_only():
    fee_by_id = {f["fee_schedule_id"]: f for f in FEES}
    lines = build(waiver_type="SIBLING")
    assert eligible_fees(lines, fee_by_id) == rs(90_000) + rs(20_000)
    lines.append(make_line(INV, 7, "SCHOLARSHIP", -rs(50_000), ISSUE, "s", applies_to=f"{INV}-L01"))
    assert eligible_fees(lines, fee_by_id) == rs(110_000)  # scholarship credits are not deducted (R-SCH-1)
