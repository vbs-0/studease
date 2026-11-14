from datetime import date
from decimal import Decimal

import pytest

from app.domain.billing import build_invoice_lines, line_net
from app.domain.scholarships import BY_CODE, SCHEMES, credit_lines, decide, judge

from .conftest import make_fee, make_student, rs

INV = "INV-STU-000001-2026-000001"
FEES = [make_fee("TUITION", 100_000), make_fee("LAB", 20_000), make_fee("LIBRARY", 5_000)]
FEE_BY_ID = {f["fee_schedule_id"]: f for f in FEES}


def gpa(v: str):
    return make_student(gpa=Decimal(v))


def test_gpa_boundary_for_merit_gold():
    assert judge(gpa("9.00"), BY_CODE["MERIT_GOLD"], True) == ("ELIGIBLE", "MEETS_CRITERIA")
    assert judge(gpa("8.99"), BY_CODE["MERIT_GOLD"], True) == ("INELIGIBLE", "GPA_BELOW_MIN")


def test_need_based_needs_low_income_and_gpa_six():
    s = BY_CODE["NEED_BASED"]
    assert judge(make_student(income_band="LOW", gpa=Decimal("6.00")), s, True)[0] == "ELIGIBLE"
    assert judge(make_student(income_band="LOW", gpa=Decimal("5.99")), s, True) == ("INELIGIBLE", "GPA_BELOW_MIN")
    assert judge(make_student(income_band="MID", gpa=Decimal("9")), s, True) == ("INELIGIBLE", "INCOME_BAND_NOT_LOW")


def test_sports_and_international_schemes_check_their_own_criterion_first():
    assert judge(make_student(gpa=Decimal("9.9")), BY_CODE["SPORTS"], True) == ("INELIGIBLE", "NOT_SPORTS_QUOTA")
    assert judge(make_student(gpa=Decimal("9.9")), BY_CODE["INTL_EXCELLENCE"], True) == \
        ("INELIGIBLE", "NOT_INTERNATIONAL")
    intl = make_student(residency="INTERNATIONAL", gpa=Decimal("8.50"))
    assert judge(intl, BY_CODE["INTL_EXCELLENCE"], True)[0] == "ELIGIBLE"


def test_not_enrolled_beats_every_other_reason():
    assert judge(gpa("9.9"), BY_CODE["MERIT_GOLD"], False) == ("INELIGIBLE", "NOT_ENROLLED")


def test_percent_award_is_a_share_of_eligible_fees():
    out = decide(gpa("9.20"), rs(120_000), ["MERIT_GOLD"])
    assert out.award.amount_paise == rs(60_000)            # 50% of 120,000
    assert out.decisions == [("MERIT_GOLD", "ELIGIBLE", "MEETS_CRITERIA")]


def test_fixed_award_is_capped_at_eligible_fees():
    out = decide(make_student(sports_quota=True, gpa=Decimal("6")), rs(20_000), ["SPORTS"])
    assert out.award.amount_paise == rs(20_000)            # fixed 30,000 cannot exceed 20,000 (R-SCH-4)


def test_largest_award_wins_and_the_loser_is_superseded():
    s = make_student(gpa=Decimal("9.2"), sports_quota=True)
    out = decide(s, rs(120_000), ["SPORTS", "MERIT_GOLD"])
    assert out.award.scheme_code == "MERIT_GOLD"           # 60,000 beats fixed 30,000
    assert dict((c, (d, r)) for c, d, r in out.decisions) == {
        "MERIT_GOLD": ("ELIGIBLE", "MEETS_CRITERIA"), "SPORTS": ("INELIGIBLE", "SUPERSEDED")}


def test_a_tie_goes_to_the_scheme_listed_first():
    s = make_student(gpa=Decimal("9.2"), sports_quota=True)
    out = decide(s, rs(60_000), ["SPORTS", "MERIT_GOLD"])  # gold 50% = 30,000 = sports fixed 30,000
    assert out.award.scheme_code == "MERIT_GOLD"


def test_no_eligible_fees_means_no_award():
    out = decide(gpa("9.5"), 0, ["MERIT_GOLD", "MERIT_SILVER"])
    assert out.award is None
    assert [(d, r) for _, d, r in out.decisions] == [("INELIGIBLE", "NO_ELIGIBLE_FEES")] * 2


def test_schemes_are_unique_by_priority_and_code():
    assert len({s.priority for s in SCHEMES}) == len(SCHEMES)
    assert len({s.code for s in SCHEMES}) == len(SCHEMES)


def lines_for(waiver=None):
    return build_invoice_lines(INV, make_student(waiver_type=waiver), FEES, date(2026, 8, 10))


def test_credit_lines_fill_tuition_first_then_lab():
    lines = lines_for()
    out = credit_lines(INV, "SCH-2026-000001", rs(110_000), lines, FEE_BY_ID, date(2026, 8, 10), 4)
    assert [(c["applies_to_line_id"][-3:], c["amount_paise"]) for c in out] == \
        [("L01", -rs(100_000)), ("L02", -rs(10_000))]
    assert [c["line_no"] for c in out] == [4, 5]


def test_credit_lines_never_exceed_a_lines_net_after_waivers():
    lines = lines_for("SIBLING")                           # tuition net 90,000
    out = credit_lines(INV, "SCH-2026-000001", rs(100_000), lines, FEE_BY_ID, date(2026, 8, 10), 5)
    assert out[0]["amount_paise"] == -rs(90_000)
    assert line_net(f"{INV}-L01", lines + out) == 0


def test_an_award_above_the_eligible_fees_is_rejected():
    with pytest.raises(ValueError, match="exceeds"):
        credit_lines(INV, "SCH-2026-000001", rs(120_001), lines_for(), FEE_BY_ID, date(2026, 8, 10), 4)
