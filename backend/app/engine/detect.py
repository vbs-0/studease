"""Exception detectors (spec 6.3). Each recomputes the figure from source rows with the domain rules and reports
a disagreement. The only input is the dataset: there is no parameter through which ground truth could enter."""
from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime

from app import ids
from app.domain import billing, ledger
from app.domain.calendar import AS_OF

Dataset = dict[str, list[dict]]
CREATED_AT = datetime(AS_OF.year, AS_OF.month, AS_OF.day, 12, 0, tzinfo=UTC)   # fixed, so detection is repeatable
ORDER = ["ALLOC_EXCEEDS_PAYMENT", "SCHOLARSHIP_EXCEEDS_ELIGIBLE", "DUPLICATE_INVOICE", "REFUND_EXCEEDS_NET_PAID",
         "BALANCE_LEDGER_MISMATCH"]


def _finding(kind: str, entity_type: str, entity_id: str, student: str, expected: int | None, found: int,
             decision: str) -> dict:
    return {"exception_type": kind, "entity_type": entity_type, "entity_id": entity_id, "student_id": student,
            "expected_paise": expected, "found_paise": found, "recommended_decision": decision}


def alloc_exceeds_payment(ds: Dataset) -> list[dict]:
    """A payment whose allocations add up to more than the payment."""
    allocated = defaultdict(int)
    for a in ds["payment_allocation"]:
        allocated[a["payment_id"]] += a["amount_paise"]
    return [_finding("ALLOC_EXCEEDS_PAYMENT", "payment", p["payment_id"], p["student_id"], p["amount_paise"],
                     allocated[p["payment_id"]], "REVERSE_ALLOCATION")
            for p in ds["payment"] if allocated[p["payment_id"]] > p["amount_paise"]]


def scholarship_exceeds_eligible(ds: Dataset) -> list[dict]:
    """An award above the scholarship-eligible fees recomputed from the invoice it was applied to (R-SCH-4)."""
    fee_by_id = {f["fee_schedule_id"]: f for f in ds["fee_schedule"]}
    lines = defaultdict(list)
    for ln in ds["invoice_line"]:
        lines[ln["invoice_id"]].append(ln)
    out = []
    for s in ds["scholarship"]:
        eligible = billing.eligible_fees(lines[s["invoice_id"]], fee_by_id)
        if s["amount_paise"] > eligible:
            out.append(_finding("SCHOLARSHIP_EXCEEDS_ELIGIBLE", "scholarship", s["scholarship_id"], s["student_id"],
                                eligible, s["amount_paise"], "CAP_SCHOLARSHIP"))
    return out


def duplicate_invoice(ds: Dataset) -> list[dict]:
    """A second invoice for an enrollment that already has one; the earliest invoice is the original."""
    by_enrollment = defaultdict(list)
    for i in ds["invoice"]:
        by_enrollment[i["enrollment_id"]].append(i)
    out = []
    for group in by_enrollment.values():
        for dup in sorted(group, key=lambda i: i["invoice_id"])[1:]:
            out.append(_finding("DUPLICATE_INVOICE", "invoice", dup["invoice_id"], dup["student_id"], 0,
                                dup["total_paise"], "VOID_DUPLICATE"))
    return out


def refund_exceeds_net_paid(ds: Dataset) -> list[dict]:
    """A refund larger than the student's payments to that date minus their earlier refunds (R-REF-2)."""
    pays, refunds = defaultdict(list), defaultdict(list)
    for p in ds["payment"]:
        pays[p["student_id"]].append(p)
    for r in ds["refund"]:
        refunds[r["student_id"]].append(r)
    out = []
    for sid, rs in refunds.items():
        earlier = 0
        for r in sorted(rs, key=lambda r: (r["approved_on"], r["refund_id"])):
            net = sum(p["amount_paise"] for p in pays[sid] if p["received_on"] <= r["approved_on"]) - earlier
            if r["amount_paise"] > net:
                out.append(_finding("REFUND_EXCEEDS_NET_PAID", "refund", r["refund_id"], sid, net,
                                    r["amount_paise"], "BLOCK_REFUND"))
            earlier += r["amount_paise"]
    return out


def balance_disagrees_with_ledger(ds: Dataset) -> list[dict]:
    """A stated balance that is not the sum of the student's ledger entries (R-LED-1, R-LED-2)."""
    entries = defaultdict(list)
    for e in ds["ledger_entry"]:
        entries[e["student_id"]].append(e)
    out = []
    for b in ds["student_balance"]:
        right = ledger.balance(entries[b["student_id"]])
        if b["balance_paise"] != right:
            out.append(_finding("BALANCE_LEDGER_MISMATCH", "student_balance", b["student_id"], b["student_id"], right,
                                b["balance_paise"], "RECOMPUTE_BALANCE"))
    return out


DETECTORS = [alloc_exceeds_payment, scholarship_exceeds_eligible, duplicate_invoice, refund_exceeds_net_paid,
             balance_disagrees_with_ledger]


def run(ds: Dataset) -> list[dict]:
    """Every exception found, as rows of the `exception` table (status OPEN), in a fixed order."""
    found = [f for detector in DETECTORS for f in detector(ds)]
    found.sort(key=lambda f: (ORDER.index(f["exception_type"]), f["entity_id"]))
    return [{"exception_id": ids.exception_id(n), **f, "status": "OPEN", "note": None, "resolved_by": None,
             "created_at": CREATED_AT, "resolved_at": None} for n, f in enumerate(found, 1)]
