"""Scholarship criteria, decisions and awards (R-SCH)."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.billing import line_net, make_line
from app.enums import FEE_TYPES
from app.money import pct


@dataclass(frozen=True)
class Scheme:
    code: str
    name: str
    min_gpa: Decimal
    required_income_band: str | None
    requires_sports_quota: bool
    requires_international: bool
    award_type: str            # PERCENT or FIXED
    award_bp: int | None       # basis points of eligible fees
    award_fixed_paise: int | None
    priority: int              # lower wins a tie


SCHEMES: tuple[Scheme, ...] = (
    Scheme("MERIT_GOLD", "Merit Gold", Decimal("9.00"), None, False, False, "PERCENT", 5000, None, 1),
    Scheme("MERIT_SILVER", "Merit Silver", Decimal("8.00"), None, False, False, "PERCENT", 2500, None, 2),
    Scheme("NEED_BASED", "Need Based", Decimal("6.00"), "LOW", False, False, "PERCENT", 4000, None, 3),
    Scheme("SPORTS", "Sports Excellence", Decimal("5.50"), None, True, False, "FIXED", None, 3_000_000, 4),
    Scheme("INTL_EXCELLENCE", "International Excellence", Decimal("8.50"), None, False, True, "PERCENT", 2000,
           None, 5),
)
BY_CODE = {s.code: s for s in SCHEMES}


@dataclass(frozen=True)
class Award:
    scheme_code: str
    amount_paise: int
    eligible_fees_paise: int


@dataclass(frozen=True)
class Outcome:
    decisions: list[tuple[str, str, str]]   # (scheme_code, decision, reason_code) per application
    award: Award | None


def judge(student: dict, scheme: Scheme, enrolled: bool) -> tuple[str, str]:
    """One application against one scheme (R-SCH-2). Structural criteria are checked before the GPA."""
    if not enrolled:
        return "INELIGIBLE", "NOT_ENROLLED"
    if scheme.requires_international and student["residency"] != "INTERNATIONAL":
        return "INELIGIBLE", "NOT_INTERNATIONAL"
    if scheme.requires_sports_quota and not student["sports_quota"]:
        return "INELIGIBLE", "NOT_SPORTS_QUOTA"
    if scheme.required_income_band and student["income_band"] != scheme.required_income_band:
        return "INELIGIBLE", "INCOME_BAND_NOT_LOW"
    if student["gpa"] < scheme.min_gpa:
        return "INELIGIBLE", "GPA_BELOW_MIN"
    return "ELIGIBLE", "MEETS_CRITERIA"


def computed_amount(scheme: Scheme, eligible: int) -> int:
    """What the scheme would give before the cap (R-SCH-4 caps it at the eligible fees)."""
    if scheme.award_type == "PERCENT":
        return pct(eligible, scheme.award_bp)
    return scheme.award_fixed_paise


def decide(student: dict, eligible_fees: int, applied: list[str], enrolled: bool = True) -> Outcome:
    """Judge every application and pick the one award (R-SCH-3, R-SCH-4).

    The largest capped amount wins; a tie goes to the scheme with the lowest priority number. Losing
    applications that met the criteria are recorded as INELIGIBLE / SUPERSEDED."""
    decisions: list[list[str]] = []
    contenders: list[tuple[Scheme, int]] = []
    for code in applied:
        scheme = BY_CODE[code]
        decision, reason = judge(student, scheme, enrolled)
        if decision == "ELIGIBLE":
            if eligible_fees <= 0:
                decision, reason = "INELIGIBLE", "NO_ELIGIBLE_FEES"
            else:
                contenders.append((scheme, min(computed_amount(scheme, eligible_fees), eligible_fees)))
        decisions.append([code, decision, reason])
    if not contenders:
        return Outcome([tuple(d) for d in decisions], None)
    winner, amount = min(contenders, key=lambda c: (-c[1], c[0].priority))
    for d in decisions:
        if d[1] == "ELIGIBLE" and d[0] != winner.code:
            d[1], d[2] = "INELIGIBLE", "SUPERSEDED"
    return Outcome([tuple(d) for d in decisions], Award(winner.code, amount, eligible_fees))


def credit_lines(invoice_id: str, scholarship_id: str, amount: int, lines: list[dict],
                 fee_by_id: dict[str, dict], posted_on: date, next_line_no: int) -> list[dict]:
    """R-SCH-5: SCHOLARSHIP credit lines, TUITION first then LAB, never above a line's net of waivers and
    earlier scholarship credits. Raises ValueError if `amount` cannot fit (it would exceed eligible fees)."""
    targets = [ln for ln in lines if ln["line_type"] == "FEE"
               and fee_by_id[ln["fee_schedule_id"]]["scholarship_eligible"]]
    targets.sort(key=lambda ln: FEE_TYPES.index(fee_by_id[ln["fee_schedule_id"]]["fee_type"]))
    remaining, out = amount, []
    for target in targets:
        room = line_net(target["invoice_line_id"], lines, ("WAIVER", "SCHOLARSHIP"))
        take = min(room, remaining)
        if take > 0:
            out.append(make_line(invoice_id, next_line_no + len(out), "SCHOLARSHIP", -take, posted_on,
                                 f"Scholarship {scholarship_id}", scholarship_id=scholarship_id,
                                 applies_to=target["invoice_line_id"]))
            remaining -= take
    if remaining > 0:
        raise ValueError(f"award {amount} exceeds the eligible fees by {remaining}")
    return out
