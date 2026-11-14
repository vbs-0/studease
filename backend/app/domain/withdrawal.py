"""Cancellations, withdrawals and refunds (R-WD, R-REF)."""
from datetime import date

from app.domain.billing import line_net, make_line, outstanding_by_line
from app.domain.calendar import Term
from app.money import pct

FULL = 10000


def classify(left_on: date, term: Term) -> str:
    """R-WD-1 and R-WD-2: leaving before the term starts is a cancellation, otherwise a withdrawal."""
    return "CANCELLED" if left_on < term.start else "WITHDRAWN"


def refund_share_bp(left_on: date, term: Term) -> int:
    """Share of net charges that is reversed, in basis points: before start 100%, days 0-14 75%,
    days 15-30 50%, later 0%."""
    if left_on < term.start:
        return FULL
    day = (left_on - term.start).days
    if day <= 14:
        return 7500
    if day <= 30:
        return 5000
    return 0


def adjustment_lines(invoice_id: str, lines: list[dict], share_bp: int, next_line_no: int,
                     posted_on: date) -> list[dict]:
    """R-WD-2: one negative ADJUSTMENT per FEE line, `share_bp` of what is left after waivers and
    scholarship. Late fees are not reduced."""
    out: list[dict] = []
    for ln in lines:
        if ln["line_type"] != "FEE":
            continue
        net = line_net(ln["invoice_line_id"], lines)
        amount = pct(net, share_bp) if net > 0 else 0
        if amount > 0:
            out.append(make_line(invoice_id, next_line_no + len(out), "ADJUSTMENT", -amount, posted_on,
                                 f"Adjustment {share_bp / 100:g}% on {ln['description']}",
                                 applies_to=ln["invoice_line_id"]))
    return out


def excess_by_line(lines: list[dict], allocations: list[dict]) -> dict[str, int]:
    """R-REF-1: per charge line, how much more was allocated than is now owed (positive numbers only)."""
    return {lid: -v for lid, v in outstanding_by_line(lines, allocations).items() if v < 0}


def plan_reversals(allocations: list[dict], excess: dict[str, int]) -> list[tuple[str, str, int]]:
    """Which payments give the excess back, newest allocation first. Returns (payment_id, line_id, amount).

    History is kept: the caller writes each result as a negative allocation row (R-REF-1)."""
    out: list[tuple[str, str, int]] = []
    for line_id, left in sorted(excess.items()):
        per_payment: dict[str, list] = {}
        for a in allocations:
            if a["invoice_line_id"] != line_id:
                continue
            rec = per_payment.setdefault(a["payment_id"], [0, a["allocated_on"], a["allocation_id"]])
            rec[0] += a["amount_paise"]
            rec[1], rec[2] = max((rec[1], rec[2]), (a["allocated_on"], a["allocation_id"]))
        for pid, (net, _, _) in sorted(per_payment.items(), key=lambda kv: (kv[1][1], kv[1][2]), reverse=True):
            if left <= 0:
                break
            take = min(left, net)
            if take > 0:
                out.append((pid, line_id, take))
                left -= take
    return out


def refund_due(excess_total: int, net_paid: int) -> int:
    """R-REF-2: the refund is the excess, but never more than the student's net paid amount."""
    return max(0, min(excess_total, net_paid))
