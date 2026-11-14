"""Invoice lines, waivers and outstanding amounts (R-BILL).

Charges are positive lines (FEE, LATE_FEE). Credits (WAIVER, SCHOLARSHIP, ADJUSTMENT) are negative lines that
point at the charge they reduce through `applies_to_line_id`; the original charge is never edited.
"""
from datetime import date

from app import ids
from app.domain.fees import eligible_fee_rows
from app.money import pct

CHARGE_TYPES = ("FEE", "LATE_FEE")

# R-BILL-2: fee type and share (basis points) each waiver removes. A student holds at most one waiver.
WAIVER_RULES: dict[str, list[tuple[str, int]]] = {
    "STAFF_WARD": [("TUITION", 10000)],
    "SIBLING": [("TUITION", 1000)],
    "HARDSHIP": [("LIBRARY", 10000), ("TECHNOLOGY", 10000), ("EXAM", 10000)],
}


def make_line(invoice_id: str, line_no: int, line_type: str, amount: int, posted_on: date, description: str,
              fee_schedule_id: str | None = None, scholarship_id: str | None = None,
              applies_to: str | None = None) -> dict:
    return {"invoice_line_id": ids.invoice_line_id(invoice_id, line_no), "invoice_id": invoice_id,
            "line_no": line_no, "line_type": line_type, "fee_schedule_id": fee_schedule_id,
            "scholarship_id": scholarship_id, "applies_to_line_id": applies_to, "description": description,
            "amount_paise": amount, "posted_on": posted_on}


def build_invoice_lines(invoice_id: str, student: dict, fee_rows: list[dict], issue_date: date) -> list[dict]:
    """FEE lines for every eligible fee row, then the student's WAIVER lines (R-BILL-1, R-BILL-2)."""
    lines: list[dict] = []
    fee_line_by_type: dict[str, dict] = {}
    for row in eligible_fee_rows(student, fee_rows, issue_date):
        line = make_line(invoice_id, len(lines) + 1, "FEE", row["amount_paise"], issue_date,
                         f"{row['fee_type'].replace('_', ' ').title()} fee", fee_schedule_id=row["fee_schedule_id"])
        lines.append(line)
        fee_line_by_type[row["fee_type"]] = line
    for fee_type, bp in WAIVER_RULES.get(student.get("waiver_type"), []):
        target = fee_line_by_type.get(fee_type)
        if target is None:
            continue
        amount = pct(target["amount_paise"], bp)
        if amount:
            lines.append(make_line(invoice_id, len(lines) + 1, "WAIVER", -amount, issue_date,
                                   f"Waiver {student['waiver_type']} on {fee_type}",
                                   applies_to=target["invoice_line_id"]))
    return lines


def credits_on(line_id: str, lines: list[dict], types: tuple[str, ...] | None = None) -> int:
    """Sum of credit lines pointing at `line_id` (negative), optionally only of the given types."""
    return sum(ln["amount_paise"] for ln in lines
               if ln["applies_to_line_id"] == line_id and (types is None or ln["line_type"] in types))


def line_net(line_id: str, lines: list[dict], types: tuple[str, ...] | None = None) -> int:
    """A charge line's amount after the credits (of the given types, default all) that point at it."""
    base = next(ln["amount_paise"] for ln in lines if ln["invoice_line_id"] == line_id)
    return base + credits_on(line_id, lines, types)


def invoice_total(lines: list[dict]) -> int:
    """R-BILL-3: the sum of every line. Computed, never typed in."""
    return sum(ln["amount_paise"] for ln in lines)


def outstanding_by_line(lines: list[dict], allocations: list[dict]) -> dict[str, int]:
    """R-BILL-4: for every charge line, net of credits minus what payments allocated to it.

    A negative value means more was allocated than is now owed (the line was reduced after payment).
    One pass over each list, so the cost is linear in the number of lines and allocations."""
    credit: dict[str, int] = {}
    for ln in lines:
        target = ln["applies_to_line_id"]
        if target is not None:
            credit[target] = credit.get(target, 0) + ln["amount_paise"]
    allocated: dict[str, int] = {}
    for a in allocations:
        allocated[a["invoice_line_id"]] = allocated.get(a["invoice_line_id"], 0) + a["amount_paise"]
    return {ln["invoice_line_id"]: ln["amount_paise"] + credit.get(ln["invoice_line_id"], 0)
            - allocated.get(ln["invoice_line_id"], 0)
            for ln in lines if ln["line_type"] in CHARGE_TYPES}


def eligible_fees(lines: list[dict], fee_by_id: dict[str, dict]) -> int:
    """R-SCH-1: scholarship-eligible FEE lines net of waivers only (scholarship credits are not deducted)."""
    return sum(line_net(ln["invoice_line_id"], lines, ("WAIVER",)) for ln in lines
               if ln["line_type"] == "FEE" and fee_by_id[ln["fee_schedule_id"]]["scholarship_eligible"])
