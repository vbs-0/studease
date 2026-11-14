"""Master data: programs, terms, scholarship schemes and fee schedules (spec 5.1, 5.2, 5.4)."""
import random
from datetime import date

from app import ids
from app.domain.calendar import TERM_ORDER, TERMS
from app.domain.scholarships import SCHEMES
from app.money import pct

PROGRAMS = [
    ("B.Tech Computer Science", "UG", True), ("B.Tech Mechanical Engineering", "UG", True),
    ("B.Tech Electronics", "UG", True), ("B.Sc Physics", "UG", True), ("B.Sc Chemistry", "UG", True),
    ("B.Sc Biotechnology", "UG", True), ("B.Com Accounting", "UG", False), ("BBA Management", "UG", False),
    ("BA Economics", "UG", False), ("BA Psychology", "UG", False),
    ("M.Tech Computer Science", "PG", True), ("MBA", "PG", False), ("M.Sc Data Science", "PG", True),
    ("M.Sc Physics", "PG", True), ("MA English", "PG", False), ("M.Com", "PG", False),
    ("Diploma Mechanical", "DIPLOMA", True), ("Diploma Electrical", "DIPLOMA", True),
    ("Diploma Information Technology", "DIPLOMA", False), ("Diploma Hospitality", "DIPLOMA", False),
]
TUITION_RANGE = {"UG": (60_000, 120_000), "PG": (90_000, 180_000), "DIPLOMA": (30_000, 50_000)}  # INR per term
INTL_SURCHARGE = {"UG": 40_000, "PG": 60_000, "DIPLOMA": 20_000}
LAB_RANGE = (15_000, 30_000)
FLAT = {"LIBRARY": 5_000, "TECHNOLOGY": 6_000, "EXAM": 4_000, "HOSTEL": 45_000}
SUMMER_BP = 4000                     # summer fees are 40% of the regular-term fee
REVISED_PROGRAMS = 8                 # FALL tuition of this many programs was revised ...
REVISION_BP = 10500                  # ... by +5% ...
REVISION_DATE = date(2026, 7, 1)     # ... effective 2026-07-01 (R-FEE-3)
EPOCH = date(2026, 1, 1)


def programs() -> list[dict]:
    assert len(PROGRAMS) == 20
    return [{"program_id": ids.program_id(i + 1), "name": n, "level": lv, "has_lab": lab}
            for i, (n, lv, lab) in enumerate(PROGRAMS)]


def terms() -> list[dict]:
    return [{"term_id": t.term_id, "term_name": t.name, "year": 2026, "start_date": t.start, "end_date": t.end,
             "invoice_issue_date": t.issue, "due_date": t.due} for t in (TERMS[n] for n in TERM_ORDER)]


def schemes() -> list[dict]:
    return [{"scheme_code": s.code, "name": s.name, "min_gpa": s.min_gpa,
             "required_income_band": s.required_income_band, "requires_sports_quota": s.requires_sports_quota,
             "requires_international": s.requires_international, "award_type": s.award_type,
             "award_bp": s.award_bp, "award_fixed_paise": s.award_fixed_paise, "priority": s.priority}
            for s in SCHEMES]


def fee_id(p: dict, term_name: str, fee_type: str, version: int) -> str:
    return ids.fee_schedule_id(p["program_id"], term_name, fee_type, version)


def fee_schedules(r: random.Random, progs: list[dict]) -> list[dict]:
    """Every program x term x applicable fee type. SUMMER is 40% of the regular fee and has no hostel."""
    revised = set(r.sample([p["program_id"] for p in progs], REVISED_PROGRAMS))
    rows: list[dict] = []
    for p in progs:
        lo, hi = TUITION_RANGE[p["level"]]
        regular = {"TUITION": r.randrange(lo, hi + 1, 1_000) * 100,
                   "LIBRARY": FLAT["LIBRARY"] * 100, "TECHNOLOGY": FLAT["TECHNOLOGY"] * 100,
                   "EXAM": FLAT["EXAM"] * 100, "INTL_SURCHARGE": INTL_SURCHARGE[p["level"]] * 100,
                   "HOSTEL": FLAT["HOSTEL"] * 100}
        if p["has_lab"]:
            regular["LAB"] = r.randrange(LAB_RANGE[0], LAB_RANGE[1] + 1, 1_000) * 100
        for term_name in TERM_ORDER:
            term = TERMS[term_name]
            for fee_type, amount in regular.items():
                if term_name == "SUMMER":
                    if fee_type == "HOSTEL":
                        continue
                    amount = pct(amount, SUMMER_BP)
                base = {"program_id": p["program_id"], "term_id": term.term_id, "fee_type": fee_type,
                        "applies_to": {"INTL_SURCHARGE": "INTERNATIONAL", "HOSTEL": "HOSTEL"}.get(fee_type, "ALL"),
                        "scholarship_eligible": fee_type in ("TUITION", "LAB")}
                if term_name == "FALL" and fee_type == "TUITION" and p["program_id"] in revised:
                    rows.append({**base, "fee_schedule_id": fee_id(p, term_name, fee_type, 1),
                                 "amount_paise": amount, "version": 1, "effective_from": EPOCH,
                                 "effective_to": date(2026, 6, 30)})
                    rows.append({**base, "fee_schedule_id": fee_id(p, term_name, fee_type, 2),
                                 "amount_paise": pct(amount, REVISION_BP), "version": 2,
                                 "effective_from": REVISION_DATE, "effective_to": None})
                else:
                    rows.append({**base, "fee_schedule_id": fee_id(p, term_name, fee_type, 1),
                                 "amount_paise": amount, "version": 1, "effective_from": EPOCH, "effective_to": None})
    cols = ["fee_schedule_id", "program_id", "term_id", "fee_type", "applies_to", "amount_paise", "version",
            "effective_from", "effective_to", "scholarship_eligible"]
    return [{c: row[c] for c in cols} for row in sorted(rows, key=lambda x: x["fee_schedule_id"])]
