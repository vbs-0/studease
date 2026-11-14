"""The append-only ledger and the balance (R-LED). Positive means the student owes money."""
from datetime import date

_LINE_TO_ENTRY = {"FEE": "CHARGE", "LATE_FEE": "LATE_FEE", "WAIVER": "WAIVER", "SCHOLARSHIP": "SCHOLARSHIP",
                  "ADJUSTMENT": "ADJUSTMENT"}


def _entry(student_id: str, entry_type: str, amount: int, posted_on: date, source_type: str,
           source_id: str) -> dict:
    return {"student_id": student_id, "entry_type": entry_type, "amount_paise": amount, "posted_on": posted_on,
            "source_type": source_type, "source_id": source_id}


def entry_for_line(student_id: str, line: dict) -> dict:
    """Charges post positive, credits negative: the line amount already carries the sign."""
    return _entry(student_id, _LINE_TO_ENTRY[line["line_type"]], line["amount_paise"], line["posted_on"],
                  "invoice_line", line["invoice_line_id"])


def entry_for_payment(payment: dict) -> dict:
    """The full amount received lowers the balance, whether or not it has been allocated yet."""
    return _entry(payment["student_id"], "PAYMENT", -payment["amount_paise"], payment["received_on"],
                  "payment", payment["payment_id"])


def entry_for_refund(refund: dict) -> dict:
    """Money returned raises the balance (the student is owed less)."""
    return _entry(refund["student_id"], "REFUND", refund["amount_paise"], refund["approved_on"],
                  "refund", refund["refund_id"])


def balance(entries: list[dict]) -> int:
    """R-LED-1."""
    return sum(e["amount_paise"] for e in entries)


def summarise(entries: list[dict]) -> dict[str, int]:
    """The stated figures stored in student_balance (R-LED-2)."""
    def total(*types: str) -> int:
        return sum(e["amount_paise"] for e in entries if e["entry_type"] in types)
    return {"charged_paise": total("CHARGE", "LATE_FEE"),
            "credits_paise": total("WAIVER", "SCHOLARSHIP", "ADJUSTMENT"),
            "paid_paise": total("PAYMENT"), "refunded_paise": total("REFUND"), "balance_paise": balance(entries)}


def identity_balance(invoice_totals: list[int], payment_amounts: list[int], refund_amounts: list[int]) -> int:
    """R-LED-3: the same number reached from invoices, payments and refunds instead of the ledger."""
    return sum(invoice_totals) - sum(payment_amounts) + sum(refund_amounts)
