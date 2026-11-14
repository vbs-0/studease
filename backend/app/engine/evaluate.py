"""Evaluation (spec 6.3): detector output against ground truth, plus the business figures."""
from __future__ import annotations

from collections import Counter, defaultdict

from app.domain import ledger
from app.enums import ISSUE_TYPES

Dataset = dict[str, list[dict]]


def _ratio(num: int, den: int) -> float | None:
    return round(num / den, 4) if den else None


def _scores(tp: int, fp: int, fn: int) -> dict:
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = round(2 * precision * recall / (precision + recall), 4) if precision and recall else \
        (0.0 if tp + fp + fn else None)
    return {"true_positives": tp, "false_positives": fp, "false_negatives": fn, "precision": precision,
            "recall": recall, "f1": f1}


def _value(exception: dict) -> int | None:
    """The figure a detector reports, in the sense ground truth states it (see anomalies.py)."""
    kind = exception["exception_type"]
    if kind == "ALLOC_EXCEEDS_PAYMENT":
        return exception["found_paise"] - exception["expected_paise"]      # the amount over the payment
    if kind == "DUPLICATE_INVOICE":
        return exception["found_paise"]                                    # the amount to void
    return exception["expected_paise"]                                     # the correct figure


def detection(exceptions: list[dict], gt: list[dict]) -> dict:
    """Match exceptions to labels on (type, entity type, entity id); score each type and overall."""
    labels = {(g["issue_type"], g["entity_type"], g["entity_id"]): g for g in gt}
    found = {(e["exception_type"], e["entity_type"], e["entity_id"]): e for e in exceptions}
    per_type, totals = {}, Counter()
    for kind in ISSUE_TYPES:
        want = {k for k in labels if k[0] == kind}
        got = {k for k in found if k[0] == kind}
        tp, fp, fn = len(want & got), len(got - want), len(want - got)
        hits = [(labels[k], found[k]) for k in want & got]
        per_type[kind] = {**_scores(tp, fp, fn), "labelled": len(want), "reported": len(got),
                          "decision_correct": sum(e["recommended_decision"] == g["expected_decision"]
                                                  for g, e in hits),
                          "value_correct": sum(_value(e) == g["expected_value_paise"] for g, e in hits)}
        totals.update(tp=tp, fp=fp, fn=fn)
    macro = [t["f1"] for t in per_type.values() if t["f1"] is not None]
    return {"per_type": per_type, "overall": _scores(totals["tp"], totals["fp"], totals["fn"]),
            "macro_f1": round(sum(macro) / len(macro), 4) if macro else None}


def business(ds: Dataset) -> dict:
    """Headline figures, all computed from source rows. Money is integer paise; rates are fractions."""
    by_type = defaultdict(int)
    for ln in ds["invoice_line"]:
        by_type[ln["line_type"]] += ln["amount_paise"]
    billed = by_type["FEE"] + by_type["LATE_FEE"]
    credits = -(by_type["WAIVER"] + by_type["SCHOLARSHIP"] + by_type["ADJUSTMENT"])
    collected = sum(p["amount_paise"] for p in ds["payment"])
    refunded = sum(r["amount_paise"] for r in ds["refund"])
    entries = defaultdict(list)
    for e in ds["ledger_entry"]:
        entries[e["student_id"]].append(e)
    balances = {s["student_id"]: ledger.balance(entries[s["student_id"]]) for s in ds["student"]}
    stated = {b["student_id"]: b["balance_paise"] for b in ds["student_balance"]}
    awards = defaultdict(lambda: {"awards": 0, "amount_paise": 0})
    for s in ds["scholarship"]:
        awards[s["scheme_code"]]["awards"] += 1
        awards[s["scheme_code"]]["amount_paise"] += s["amount_paise"]
    invoices = len(ds["invoice"])
    late = sum(1 for ln in ds["invoice_line"] if ln["line_type"] == "LATE_FEE")
    receivable = billed - credits
    return {
        "billed_paise": billed, "waived_paise": -by_type["WAIVER"], "scholarships_paise": -by_type["SCHOLARSHIP"],
        "adjustments_paise": -by_type["ADJUSTMENT"], "net_receivable_paise": receivable,
        "collected_paise": collected, "refunded_paise": refunded, "net_collected_paise": collected - refunded,
        "outstanding_paise": sum(v for v in balances.values() if v > 0),
        "credit_held_paise": -sum(v for v in balances.values() if v < 0),
        "collection_rate": _ratio(collected - refunded, receivable),
        "reconciliation_rate": _ratio(sum(1 for s, v in balances.items() if stated[s] == v), len(balances)),
        "late_fee_incidence": _ratio(late, invoices), "invoices": invoices,
        "invoice_status": dict(sorted(Counter(i["status"] for i in ds["invoice"]).items())),
        "payment_status": dict(sorted(Counter(p["status"] for p in ds["payment"]).items())),
        "enrollment_status": dict(sorted(Counter(e["status"] for e in ds["enrollment"]).items())),
        "awards_by_scheme": {k: awards[k] for k in sorted(awards)},
    }


def run(exceptions: list[dict], gt: list[dict], ds: Dataset) -> dict:
    return {"detection": detection(exceptions, gt), "business": business(ds),
            "exceptions_reported": len(exceptions), "labelled_cases": len(gt)}
