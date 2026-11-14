"""Derived statuses (R-STAT) and the allowed lifecycle transitions (spec section 4)."""
from datetime import date

INITIAL = None
TRANSITIONS: dict[str, dict[str | None, set[str]]] = {
    "enrollment": {None: {"ENROLLED"}, "ENROLLED": {"COMPLETED", "WITHDRAWN", "CANCELLED"}},
    "invoice": {None: {"ISSUED"},
                "ISSUED": {"PARTIALLY_PAID", "PAID", "OVERDUE", "CANCELLED", "VOID"},
                "PARTIALLY_PAID": {"PAID", "OVERDUE", "CANCELLED"},
                "OVERDUE": {"PAID", "CANCELLED"},
                "PAID": {"CANCELLED"}},
    "eligibility": {None: {"ELIGIBLE", "INELIGIBLE"}},
    "scholarship": {None: {"AWARDED"}, "AWARDED": {"APPLIED", "REVOKED"}, "APPLIED": {"REVOKED"}},
    "payment": {None: {"RECEIVED"}, "RECEIVED": {"PARTIALLY_ALLOCATED", "ALLOCATED"},
                "PARTIALLY_ALLOCATED": {"ALLOCATED"}, "ALLOCATED": {"PARTIALLY_ALLOCATED"}},
    "refund": {None: {"APPROVED"}, "APPROVED": {"PAID"}},
    "exception": {None: {"OPEN"}, "OPEN": {"RESOLVED", "DISMISSED"}},
}


def is_allowed(entity: str, current: str | None, new: str) -> bool:
    return new in TRANSITIONS[entity].get(current, set())


def invoice_status(voided: bool, cancelled: bool, outstanding: int, allocated: int, due: date,
                   as_of: date) -> str:
    """R-STAT, first match wins: VOID, CANCELLED, PAID, OVERDUE, PARTIALLY_PAID, ISSUED."""
    if voided:
        return "VOID"
    if cancelled:
        return "CANCELLED"
    if outstanding <= 0:
        return "PAID"
    if as_of > due:
        return "OVERDUE"
    if allocated > 0:
        return "PARTIALLY_PAID"
    return "ISSUED"


def payment_status(amount: int, allocated: int, refunded: int) -> str:
    """ALLOCATED once nothing is left unapplied; a refund counts as applying the money."""
    unapplied = amount - allocated - refunded
    if unapplied <= 0:
        return "ALLOCATED"
    return "PARTIALLY_ALLOCATED" if allocated > 0 or refunded > 0 else "RECEIVED"
