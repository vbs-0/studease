"""Labelled anomalies injected after the valid baseline (spec 6.1).

Each case is injected on its own students (an anomaly never touches a student that carries another one). Derived
values are NOT recomputed afterwards: that disagreement is exactly what a detector must find. The labels are
returned separately as ground truth and are never written into any input table.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from app import ids
from app.datagen.rand import stream
from app.datagen.scale import Scale
from app.domain import billing, status
from app.domain.calendar import AS_OF
from app.money import pct

Dataset = dict[str, list[dict]]


class _Pool:
    """Hands out students one at a time, never twice, in a seeded order."""
    def __init__(self, r) -> None:
        self.r, self.used = r, set()

    def pick(self, candidates: list[tuple[str, object]], k: int, label: str) -> list[tuple[str, object]]:
        pool = [c for c in sorted(candidates, key=lambda c: c[0]) if c[0] not in self.used]
        self.r.shuffle(pool)
        chosen, seen = [], set()
        for sid, payload in pool:
            if sid in seen:
                continue
            chosen.append((sid, payload))
            seen.add(sid)
            if len(chosen) == k:
                break
        if len(chosen) < k:
            raise ValueError(f"{label}: only {len(chosen)} suitable students, {k} needed")
        self.used |= seen
        return chosen


def _truth(rows: list[dict], issue: str, entity: str, entity_id: str, student: str, decision: str,
           value: int | None, details: str) -> None:
    rows.append({"issue_type": issue, "entity_type": entity, "entity_id": entity_id, "student_id": student,
                 "expected_decision": decision, "expected_value_paise": value, "details": details})


def inject(ds: Dataset, scale: Scale, seed: int) -> list[dict]:
    """Mutate `ds` on the chosen students and return the ground-truth rows (with ids), in issue-type order."""
    r = stream(seed, "anomalies")
    pool = _Pool(r)
    counts = scale.anomalies
    truth: list[dict] = []

    alloc_sum, allocs_n = defaultdict(int), defaultdict(int)
    for a in ds["payment_allocation"]:
        alloc_sum[a["payment_id"]] += a["amount_paise"]
        allocs_n[a["payment_id"]] += 1
    refunded_payments = {x["payment_id"] for x in ds["refund"] if x["payment_id"]}
    payments_of = defaultdict(list)
    for p in ds["payment"]:
        payments_of[p["student_id"]].append(p)
    refund_total = defaultdict(int)
    for x in ds["refund"]:
        refund_total[x["student_id"]] += x["amount_paise"]
    lines_of = defaultdict(list)
    for ln in ds["invoice_line"]:
        lines_of[ln["invoice_id"]].append(ln)
    invoices_of = defaultdict(list)
    for i in ds["invoice"]:
        invoices_of[i["student_id"]].append(i)
    enrollment = {e["enrollment_id"]: e for e in ds["enrollment"]}
    events = ds["event"]

    def emit(on, etype, eid, frm, to):
        events.append({"event_id": ids.event_id(len(events) + 1), "entity_type": etype, "entity_id": eid,
                       "from_status": frm, "to_status": to, "occurred_on": on, "actor": "SYSTEM"})

    # 1. payment allocated beyond its amount ------------------------------------------------------------
    cands = [(p["student_id"], p) for p in ds["payment"]
             if alloc_sum[p["payment_id"]] == p["amount_paise"] and p["payment_id"] not in refunded_payments]
    for sid, p in pool.pick(cands, counts["ALLOC_EXCEEDS_PAYMENT"], "ALLOC_EXCEEDS_PAYMENT"):
        target = next(ln for inv in sorted(invoices_of[sid], key=lambda i: i["invoice_id"])
                      for ln in lines_of[inv["invoice_id"]] if ln["line_type"] == "FEE")
        extra = max(pct(p["amount_paise"], r.randint(500, 2500)), 10_000)
        pid = p["payment_id"]
        ds["payment_allocation"].append({
            "allocation_id": ids.allocation_id(pid, allocs_n[pid] + 1), "payment_id": pid,
            "invoice_line_id": target["invoice_line_id"], "amount_paise": extra,
            "allocated_on": max(min(AS_OF, p["received_on"] + timedelta(days=1)), target["posted_on"])})
        _truth(truth, "ALLOC_EXCEEDS_PAYMENT", "payment", pid, sid, "REVERSE_ALLOCATION", extra,
               f"an extra allocation of {extra} paise on a fully allocated payment of {p['amount_paise']}")

    # 2. scholarship above the eligible fees ------------------------------------------------------------
    cands = [(s["student_id"], s) for s in ds["scholarship"] if s["status"] == "APPLIED"]
    for sid, s in pool.pick(cands, counts["SCHOLARSHIP_EXCEEDS_ELIGIBLE"], "SCHOLARSHIP_EXCEEDS_ELIGIBLE"):
        cap = s["eligible_fees_paise"]
        s["amount_paise"] = cap + max(pct(cap, r.randint(1000, 4000)), 100_000)
        _truth(truth, "SCHOLARSHIP_EXCEEDS_ELIGIBLE", "scholarship", s["scholarship_id"], sid, "CAP_SCHOLARSHIP",
               cap, f"award raised to {s['amount_paise']} paise against eligible fees of {cap}")

    # 3. invoice generated twice ------------------------------------------------------------------------
    cands = [(i["student_id"], i) for i in ds["invoice"]
             if enrollment[i["enrollment_id"]]["status"] in ("ENROLLED", "COMPLETED") and i["total_paise"] > 0]
    next_seq = len(ds["invoice"])
    for sid, inv in pool.pick(cands, counts["DUPLICATE_INVOICE"], "DUPLICATE_INVOICE"):
        next_seq += 1
        new_id = ids.invoice_id(ids.student_no(sid), next_seq)
        original = [ln for ln in lines_of[inv["invoice_id"]] if ln["posted_on"] == inv["issue_date"]
                    and ln["line_type"] in ("FEE", "WAIVER", "SCHOLARSHIP")]
        new_id_of = {ln["invoice_line_id"]: ids.invoice_line_id(new_id, ln["line_no"]) for ln in original}
        copies = [{**ln, "invoice_line_id": new_id_of[ln["invoice_line_id"]], "invoice_id": new_id,
                   "applies_to_line_id": new_id_of.get(ln["applies_to_line_id"])} for ln in original]
        total = billing.invoice_total(copies)
        ds["invoice_line"] += copies
        ds["invoice"].append({**inv, "invoice_id": new_id, "total_paise": total,
                              "status": status.invoice_status(False, False, total, 0, inv["due_date"], AS_OF)})
        emit(inv["issue_date"], "invoice", new_id, None, "ISSUED")
        if inv["due_date"] + timedelta(days=1) <= AS_OF:
            emit(inv["due_date"] + timedelta(days=1), "invoice", new_id, "ISSUED", "OVERDUE")
        _truth(truth, "DUPLICATE_INVOICE", "invoice", new_id, sid, "VOID_DUPLICATE", total,
               f"second invoice for {inv['enrollment_id']}; the first is {inv['invoice_id']}")

    # 4. refund above what the student has net paid -----------------------------------------------------
    cands = [(sid, ps) for sid, ps in payments_of.items()
             if sum(p["amount_paise"] for p in ps) - refund_total[sid] > 0]
    for sid, ps in pool.pick(cands, counts["REFUND_EXCEEDS_NET_PAID"], "REFUND_EXCEEDS_NET_PAID"):
        net = sum(p["amount_paise"] for p in ps) - refund_total[sid]
        last = max(ps, key=lambda p: (p["received_on"], p["payment_id"]))
        amount = net + max(pct(net, r.randint(500, 3000)), 100_000)
        rid = ids.refund_id(len(ds["refund"]) + 1)
        approved = max(last["received_on"], AS_OF - timedelta(days=r.randint(1, 15)))
        ds["refund"].append({"refund_id": rid, "student_id": sid, "invoice_id": None,
                             "payment_id": last["payment_id"], "amount_paise": amount, "reason": "OVERPAYMENT",
                             "status": "APPROVED", "approved_on": approved, "paid_on": None})
        emit(approved, "refund", rid, None, "APPROVED")
        _truth(truth, "REFUND_EXCEEDS_NET_PAID", "refund", rid, sid, "BLOCK_REFUND", net,
               f"refund of {amount} paise against a net paid amount of {net}")

    # 5. stated balance disagrees with the ledger -------------------------------------------------------
    by_student = {b["student_id"]: b for b in ds["student_balance"]}
    cands = [(sid, b) for sid, b in by_student.items()]
    for sid, b in pool.pick(cands, counts["BALANCE_LEDGER_MISMATCH"], "BALANCE_LEDGER_MISMATCH"):
        right = b["balance_paise"]
        b["balance_paise"] = right + r.choice([-1, 1]) * r.randint(5, 200) * 100
        _truth(truth, "BALANCE_LEDGER_MISMATCH", "student_balance", sid, sid, "RECOMPUTE_BALANCE", right,
               f"stated balance {b['balance_paise']} paise, ledger sum {right}")

    for name, key in (("payment_allocation", "allocation_id"), ("invoice", "invoice_id"),
                      ("invoice_line", "invoice_line_id"), ("refund", "refund_id")):
        ds[name].sort(key=lambda row: row[key])
    for n, row in enumerate(truth, 1):
        row["gt_id"] = ids.gt_id(n)
    return [{"gt_id": row["gt_id"], **{k: v for k, v in row.items() if k != "gt_id"}} for row in truth]
