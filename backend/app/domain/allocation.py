"""Allocating a payment to open invoice lines (R-PAY)."""
from app.domain.billing import outstanding_by_line


def allocate(amount: int, open_lines: list[tuple[str, int]]) -> tuple[list[tuple[str, int]], int]:
    """Apply `amount` to `open_lines` in the order given (R-PAY-1, R-PAY-2).

    Returns the allocations and the unapplied remainder (R-PAY-3). Never allocates more than a line's
    outstanding amount, and the allocations plus the remainder always add up to `amount`."""
    out: list[tuple[str, int]] = []
    left = amount
    for line_id, outstanding in open_lines:
        if left <= 0:
            break
        if outstanding <= 0:
            continue
        take = min(left, outstanding)
        out.append((line_id, take))
        left -= take
    return out, left


def open_lines(invoices: list[dict], lines: list[dict], allocations: list[dict]) -> list[tuple[str, int]]:
    """A student's charge lines with something still owed, oldest due date first, then by line number
    (R-PAY-1). `invoices` must already exclude voided or cancelled ones and ones not yet issued."""
    invoice_ids = {i["invoice_id"] for i in invoices}
    due = {i["invoice_id"]: i["due_date"] for i in invoices}
    mine = [ln for ln in lines if ln["invoice_id"] in invoice_ids]
    owed = outstanding_by_line(mine, allocations)
    by_id = {ln["invoice_line_id"]: ln for ln in mine}
    ordered = sorted((lid for lid, v in owed.items() if v > 0),
                     key=lambda lid: (due[by_id[lid]["invoice_id"]], by_id[lid]["invoice_id"],
                                      by_id[lid]["line_no"]))
    return [(lid, owed[lid]) for lid in ordered]
