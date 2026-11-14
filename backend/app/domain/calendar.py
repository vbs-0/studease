"""Terms and dates (spec 5.1)."""
from dataclasses import dataclass
from datetime import date, timedelta

YEAR = 2026
AS_OF = date(2026, 10, 22)      # the date every derived status and balance is stated as of
GRACE_DAYS = 7                  # R-LATE-1
PAYMENT_TERM_DAYS = 30          # due date = issue date + 30 days


@dataclass(frozen=True)
class Term:
    term_id: str
    name: str
    start: date
    end: date
    issue: date
    due: date


def _term(name: str, start: date, end: date, issue: date) -> Term:
    return Term(f"TERM-{YEAR}-{name}", name, start, end, issue, issue + timedelta(days=PAYMENT_TERM_DAYS))


TERM_ORDER = ("SPRING", "SUMMER", "FALL")
TERMS: dict[str, Term] = {
    "SPRING": _term("SPRING", date(2026, 1, 12), date(2026, 5, 8), date(2026, 1, 5)),
    "SUMMER": _term("SUMMER", date(2026, 5, 25), date(2026, 7, 31), date(2026, 5, 18)),
    "FALL": _term("FALL", date(2026, 8, 17), date(2026, 12, 11), date(2026, 8, 10)),
}
BY_ID: dict[str, Term] = {t.term_id: t for t in TERMS.values()}


def term_of(term_id: str) -> Term:
    return BY_ID[term_id]
