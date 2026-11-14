from datetime import date

import pytest

from app.domain.fees import eligible_fee_rows, is_effective

from .conftest import make_fee, make_student

ISSUE = date(2026, 8, 10)  # FALL invoice issue date


def types(rows):
    return [r["fee_type"] for r in rows]


def test_domestic_non_hostel_student_gets_only_universal_fees():
    rows = [make_fee("TUITION", 100_000), make_fee("INTL_SURCHARGE", 20_000, "INTERNATIONAL"),
            make_fee("HOSTEL", 40_000, "HOSTEL")]
    assert types(eligible_fee_rows(make_student(), rows, ISSUE)) == ["TUITION"]


def test_international_hostel_student_gets_surcharge_and_hostel():
    rows = [make_fee("HOSTEL", 40_000, "HOSTEL"), make_fee("INTL_SURCHARGE", 20_000, "INTERNATIONAL"),
            make_fee("TUITION", 100_000)]
    got = eligible_fee_rows(make_student(residency="INTERNATIONAL", hostel_resident=True), rows, ISSUE)
    assert types(got) == ["TUITION", "INTL_SURCHARGE", "HOSTEL"]  # fee-type order, not input order


def test_fall_invoice_uses_the_revised_tuition_not_the_old_one():
    """R-FEE-3: V1 ends 2026-06-30, V2 starts 2026-07-01; FALL invoices issue on 2026-08-10."""
    v1 = make_fee("TUITION", 100_000, frm=date(2026, 1, 1), to=date(2026, 6, 30), version=1)
    v2 = make_fee("TUITION", 105_000, frm=date(2026, 7, 1), version=2)
    (row,) = eligible_fee_rows(make_student(), [v1, v2], ISSUE)
    assert row["version"] == 2 and row["amount_paise"] == 105_000 * 100


def test_effective_range_is_inclusive_on_both_ends():
    row = make_fee("TUITION", 1, frm=date(2026, 7, 1), to=date(2026, 7, 31))
    assert not is_effective(row, date(2026, 6, 30))
    assert is_effective(row, date(2026, 7, 1))
    assert is_effective(row, date(2026, 7, 31))
    assert not is_effective(row, date(2026, 8, 1))


def test_row_that_ended_the_day_before_issue_is_excluded():
    row = make_fee("TUITION", 1, to=date(2026, 8, 9))
    assert eligible_fee_rows(make_student(), [row], ISSUE) == []


def test_row_effective_exactly_on_issue_date_is_included():
    row = make_fee("TUITION", 1, frm=ISSUE)
    assert types(eligible_fee_rows(make_student(), [row], ISSUE)) == ["TUITION"]


def test_overlapping_versions_are_rejected_not_double_billed():
    v1 = make_fee("TUITION", 100_000, version=1)
    v2 = make_fee("TUITION", 105_000, version=2)
    with pytest.raises(ValueError, match="overlapping"):
        eligible_fee_rows(make_student(), [v1, v2], ISSUE)
