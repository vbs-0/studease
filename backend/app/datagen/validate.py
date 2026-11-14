"""Validation (spec 6.2). Runs on the dataset alone, no database.

Nine checks. A violation is EXPECTED when the student carries a ground-truth label whose issue type is allowed to
cause that rule; every other violation is UNEXPECTED and fails the run. The run also fails if a labelled case
produced no violation at all, which would mean the checks cannot see it.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import timedelta

from app import ids, schema
from app.datagen.scale import Scale
from app.domain import billing, ledger, status
from app.domain.calendar import AS_OF, GRACE_DAYS
from app.domain.latefees import late_fee

Dataset = dict[str, list[dict]]

# Which rules a labelled case may legitimately break. "late_fee_amount" is listed for ALLOC_EXCEEDS_PAYMENT because
# the injected extra allocation is dated before a late fee was posted: recomputing "what was owed" from the stored
# rows then differs from what the simulation saw. It is a downstream effect of the label, not a separate fault.
EXPLAINS = {
    "ALLOC_EXCEEDS_PAYMENT": {"alloc_le_payment", "alloc_le_line", "late_fee_amount"},
    "SCHOLARSHIP_EXCEEDS_ELIGIBLE": {"scholarship_le_eligible", "scholarship_matches_credit"},
    "DUPLICATE_INVOICE": {"one_invoice_per_enrollment", "balance_identity"},
    "REFUND_EXCEEDS_NET_PAID": {"refund_le_net_paid", "balance_identity"},
    "BALANCE_LEDGER_MISMATCH": {"balance_matches_ledger", "balance_components", "balance_identity"},
}
CHECKS = [("C1", "Primary keys are unique and well formed"), ("C2", "Foreign keys resolve"),
          ("C3", "Enums, required fields and lengths"), ("C4", "Date ordering"),
          ("C5", "Arithmetic and business rules reconcile"), ("C6", "Lifecycle transitions are legal"),
          ("C7", "No duplicates"), ("C8", "Volume targets are met"), ("C9", "Ground truth does not leak")]


class V(tuple):
    """A violation: (rule, table, key, student_id, message)."""


def _v(rule, table, key, student, message) -> V:
    return V((rule, table, key, student, message))


class Index:
    """Lookups shared by the checks."""
    def __init__(self, ds: Dataset) -> None:
        self.ds = ds
        self.student = {s["student_id"]: s for s in ds["student"]}
        self.invoice = {i["invoice_id"]: i for i in ds["invoice"]}
        self.payment = {p["payment_id"]: p for p in ds["payment"]}
        self.line = {ln["invoice_line_id"]: ln for ln in ds["invoice_line"]}
        self.enrollment = {e["enrollment_id"]: e for e in ds["enrollment"]}
        self.fee = {f["fee_schedule_id"]: f for f in ds["fee_schedule"]}
        self.lines_of = defaultdict(list)
        for ln in ds["invoice_line"]:
            self.lines_of[ln["invoice_id"]].append(ln)
        self.allocs_of_payment = defaultdict(list)
        self.allocs_of_line = defaultdict(list)
        for a in ds["payment_allocation"]:
            self.allocs_of_payment[a["payment_id"]].append(a)
            self.allocs_of_line[a["invoice_line_id"]].append(a)
        self.owner: dict[str, str] = {}
        for table, key in (("enrollment", "enrollment_id"), ("invoice", "invoice_id"),
                           ("eligibility", "eligibility_id"), ("scholarship", "scholarship_id"),
                           ("payment", "payment_id"), ("refund", "refund_id")):
            for row in ds[table]:
                self.owner[row[key]] = row["student_id"]
        for s in self.student:
            self.owner[s] = s
        for ln in ds["invoice_line"]:
            self.owner[ln["invoice_line_id"]] = self.invoice[ln["invoice_id"]]["student_id"] \
                if ln["invoice_id"] in self.invoice else None


def _owner(ix: Index, table: str, row: dict) -> str | None:
    if "student_id" in row:
        return row["student_id"]
    if table == "payment_allocation":
        return ix.owner.get(row["payment_id"])
    if table == "event":
        return ix.owner.get(row["entity_id"])
    return None


# ----------------------------------------------------------------------------------------------- checks
def c1_keys(ix: Index):
    out, n = [], 0
    for name in schema.DATA_TABLES:
        pk = schema.TABLES[name].primary_key.columns.keys()[0]
        seen = set()
        for row in ix.ds[name]:
            n += 1
            key = row[pk]
            if key in seen:
                out.append(_v("pk_unique", name, key, _owner(ix, name, row), "duplicate primary key"))
            seen.add(key)
            if not ids.matches(name, key):
                out.append(_v("pk_format", name, key, _owner(ix, name, row), "malformed id"))
    for inv in ix.ds["invoice"]:                    # ids that embed their parents must agree with the columns
        if not inv["invoice_id"].startswith(f"INV-STU-{ids.student_no(inv['student_id']):06d}-"):
            out.append(_v("id_consistent", "invoice", inv["invoice_id"], inv["student_id"], "student not in id"))
    for ln in ix.ds["invoice_line"]:
        if ln["invoice_line_id"] != ids.invoice_line_id(ln["invoice_id"], ln["line_no"]):
            out.append(_v("id_consistent", "invoice_line", ln["invoice_line_id"], None, "id != invoice + line_no"))
    for a in ix.ds["payment_allocation"]:
        if not a["allocation_id"].startswith(f"ALLOC-{a['payment_id']}-"):
            out.append(_v("id_consistent", "payment_allocation", a["allocation_id"], None, "payment not in id"))
    for e in ix.ds["enrollment"]:
        if e["enrollment_id"] != ids.enrollment_id(ids.student_no(e["student_id"]), e["term_id"].split("-")[2]):
            out.append(_v("id_consistent", "enrollment", e["enrollment_id"], e["student_id"], "id != student + term"))
    return n, out


def c2_foreign_keys(ix: Index):
    pks = {name: {r[schema.TABLES[name].primary_key.columns.keys()[0]] for r in ix.ds[name]}
           for name in schema.DATA_TABLES}
    out, n = [], 0
    for name in schema.DATA_TABLES:
        pk = schema.TABLES[name].primary_key.columns.keys()[0]
        for fk in schema.TABLES[name].foreign_keys:
            col, parent = fk.parent.name, fk.column.table.name
            for row in ix.ds[name]:
                n += 1
                if row[col] is not None and row[col] not in pks[parent]:
                    out.append(_v("fk_resolves", name, row[pk], _owner(ix, name, row),
                                  f"{col}={row[col]} not in {parent}"))
    return n, out


def c3_domain(ix: Index):
    out, n = [], 0
    for name in schema.DATA_TABLES:
        cols = list(schema.TABLES[name].columns)
        pk = schema.TABLES[name].primary_key.columns.keys()[0]
        for row in ix.ds[name]:
            for c in cols:
                n += 1
                v = row[c.name]
                if v is None:
                    if not c.nullable:
                        out.append(_v("required", name, row[pk], _owner(ix, name, row), f"{c.name} is empty"))
                    continue
                allowed = c.info.get("allowed")
                if allowed and v not in allowed:
                    out.append(_v("enum", name, row[pk], _owner(ix, name, row), f"{c.name}={v}"))
                length = getattr(c.type, "length", None)
                if length and isinstance(v, str) and len(v) > length:
                    out.append(_v("length", name, row[pk], _owner(ix, name, row), f"{c.name} too long"))
    return n, out


def c4_dates(ix: Index):
    out, n = [], 0
    ds = ix.ds

    def check(ok: bool, rule, table, key, student, msg):
        nonlocal n
        n += 1
        if not ok:
            out.append(_v(rule, table, key, student, msg))
    for t in ds["term"]:
        check(t["invoice_issue_date"] < t["start_date"] <= t["end_date"], "term_dates", "term", t["term_id"], None,
              "issue < start <= end")
    for f in ds["fee_schedule"]:
        check(f["effective_to"] is None or f["effective_from"] <= f["effective_to"], "fee_dates", "fee_schedule",
              f["fee_schedule_id"], None, "effective range reversed")
    for e in ds["enrollment"]:
        check(e["left_on"] is None or e["enrolled_on"] <= e["left_on"], "enrollment_dates", "enrollment",
              e["enrollment_id"], e["student_id"], "left before enrolling")
    for i in ds["invoice"]:
        check(i["issue_date"] <= i["due_date"], "invoice_dates", "invoice", i["invoice_id"], i["student_id"],
              "due before issue")
    for ln in ds["invoice_line"]:
        inv = ix.invoice.get(ln["invoice_id"])
        check(inv is None or ln["posted_on"] >= inv["issue_date"], "line_dates", "invoice_line",
              ln["invoice_line_id"], inv and inv["student_id"], "posted before the invoice was issued")
    for p in ds["payment"]:
        check(p["received_on"] <= AS_OF, "payment_dates", "payment", p["payment_id"], p["student_id"],
              "received after the as-of date")
    for a in ds["payment_allocation"]:
        p, ln = ix.payment.get(a["payment_id"]), ix.line.get(a["invoice_line_id"])
        check(p is None or ln is None or a["allocated_on"] >= max(p["received_on"], ln["posted_on"]),
              "allocation_dates", "payment_allocation", a["allocation_id"], p and p["student_id"],
              "allocated before the payment or the line existed")
    for r in ds["refund"]:
        p = ix.payment.get(r["payment_id"]) if r["payment_id"] else None
        check(p is None or r["approved_on"] >= p["received_on"], "refund_dates", "refund", r["refund_id"],
              r["student_id"], "refunded before the payment")
        check(r["paid_on"] is None or r["paid_on"] >= r["approved_on"], "refund_dates", "refund", r["refund_id"],
              r["student_id"], "paid before approval")
    for s in ds["scholarship"]:
        inv = ix.invoice.get(s["invoice_id"])
        check(inv is None or s["awarded_on"] <= inv["issue_date"], "award_dates", "scholarship",
              s["scholarship_id"], s["student_id"], "awarded after the invoice was issued")
    return n, out


def c5_arithmetic(ix: Index):
    out, n = [], 0
    ds = ix.ds

    def check(ok: bool, rule, table, key, student, msg):
        nonlocal n
        n += 1
        if not ok:
            out.append(_v(rule, table, key, student, msg))

    for inv in ds["invoice"]:
        lines = ix.lines_of[inv["invoice_id"]]
        check(inv["total_paise"] == billing.invoice_total(lines), "invoice_total", "invoice", inv["invoice_id"],
              inv["student_id"], "total != sum of lines")
    for p in ds["payment"]:
        paid = sum(a["amount_paise"] for a in ix.allocs_of_payment[p["payment_id"]])
        check(paid <= p["amount_paise"], "alloc_le_payment", "payment", p["payment_id"], p["student_id"],
              f"allocated {paid} of {p['amount_paise']}")
    for inv in ds["invoice"]:
        lines = ix.lines_of[inv["invoice_id"]]
        allocs = [a for ln in lines for a in ix.allocs_of_line.get(ln["invoice_line_id"], [])]
        for lid, v in billing.outstanding_by_line(lines, allocs).items():
            check(v >= 0, "alloc_le_line", "invoice_line", lid, inv["student_id"], f"{-v} paid above what is owed")
    # term-specific fees: FEE and WAIVER lines equal what the schedule says for that student on the issue date
    fees_by = defaultdict(list)
    for f in ds["fee_schedule"]:
        fees_by[(f["program_id"], f["term_id"])].append(f)
    for inv in ds["invoice"]:
        enr, stu = ix.enrollment[inv["enrollment_id"]], ix.student[inv["student_id"]]
        want = billing.build_invoice_lines(inv["invoice_id"], stu, fees_by[(enr["program_id"], enr["term_id"])],
                                           inv["issue_date"])
        got = [ln for ln in ix.lines_of[inv["invoice_id"]]
               if ln["line_type"] in ("FEE", "WAIVER") and ln["posted_on"] == inv["issue_date"]]
        key = lambda ln: (ln["line_no"], ln["line_type"], ln["fee_schedule_id"], ln["applies_to_line_id"],  # noqa: E731
                          ln["amount_paise"])
        check([key(x) for x in want] == [key(x) for x in sorted(got, key=lambda x: x["line_no"])],
              "fees_match_schedule", "invoice", inv["invoice_id"], inv["student_id"],
              "fee or waiver lines differ from the schedule effective on the issue date")
    # scholarships
    credit = defaultdict(int)                     # credit lines of a scholarship on the invoice it belongs to
    for ln in ds["invoice_line"]:
        if ln["line_type"] == "SCHOLARSHIP":
            credit[(ln["scholarship_id"], ln["invoice_id"])] -= ln["amount_paise"]
    for s in ds["scholarship"]:
        lines = ix.lines_of.get(s["invoice_id"], [])
        eligible = billing.eligible_fees(lines, ix.fee) if lines else 0
        check(s["amount_paise"] <= min(eligible, s["eligible_fees_paise"]), "scholarship_le_eligible", "scholarship",
              s["scholarship_id"], s["student_id"], f"award {s['amount_paise']} above eligible fees {eligible}")
        on_own_invoice = credit[(s["scholarship_id"], s["invoice_id"])]
        check(on_own_invoice == s["amount_paise"], "scholarship_matches_credit", "scholarship",
              s["scholarship_id"], s["student_id"], "award differs from its credit lines")
    # late fees: one per invoice, on due + 8 days, 2% of what was owed (floor 500, cap 5,000)
    for inv in ds["invoice"]:
        late = [ln for ln in ix.lines_of[inv["invoice_id"]] if ln["line_type"] == "LATE_FEE"]
        if not late:
            continue
        check(len(late) == 1, "one_late_fee", "invoice", inv["invoice_id"], inv["student_id"], "several late fees")
        day = late[0]["posted_on"]
        check(day == inv["due_date"] + timedelta(days=GRACE_DAYS + 1), "late_fee_date", "invoice",
              inv["invoice_id"], inv["student_id"], "late fee not on due + 8 days")
        before = [ln for ln in ix.lines_of[inv["invoice_id"]] if ln is not late[0]
                  and (ln["posted_on"] < day or (ln["posted_on"] == day and ln["line_type"] != "ADJUSTMENT"))]
        allocs = [a for ln in before for a in ix.allocs_of_line.get(ln["invoice_line_id"], [])
                  if a["allocated_on"] < day or (a["allocated_on"] == day and a["amount_paise"] > 0)]
        owed = sum(v for v in billing.outstanding_by_line(before, allocs).values() if v > 0)
        check(late[0]["amount_paise"] == late_fee(owed), "late_fee_amount", "invoice", inv["invoice_id"],
              inv["student_id"], f"late fee {late[0]['amount_paise']} != 2% of {owed}")
    # refunds never exceed what the student has net paid at that moment
    pays, refs = defaultdict(list), defaultdict(list)
    for p in ds["payment"]:
        pays[p["student_id"]].append(p)
    for r in ds["refund"]:
        refs[r["student_id"]].append(r)
    for sid, rs in refs.items():
        earlier = 0
        for r in sorted(rs, key=lambda r: (r["approved_on"], r["refund_id"])):
            net = sum(p["amount_paise"] for p in pays[sid] if p["received_on"] <= r["approved_on"]) - earlier
            check(r["amount_paise"] <= net, "refund_le_net_paid", "refund", r["refund_id"], sid,
                  f"refund {r['amount_paise']} above net paid {net}")
            earlier += r["amount_paise"]
    # balances reconcile three ways
    led = defaultdict(list)
    for e in ds["ledger_entry"]:
        led[e["student_id"]].append(e)
    totals, paid_sum, refund_sum = defaultdict(int), defaultdict(int), defaultdict(int)
    for inv in ds["invoice"]:
        totals[inv["student_id"]] += inv["total_paise"]
    for p in ds["payment"]:
        paid_sum[p["student_id"]] += p["amount_paise"]
    for r in ds["refund"]:
        refund_sum[r["student_id"]] += r["amount_paise"]
    for b in ds["student_balance"]:
        sid = b["student_id"]
        entries = led[sid]
        check(b["balance_paise"] == ledger.balance(entries), "balance_matches_ledger", "student_balance", sid, sid,
              f"stated {b['balance_paise']}, ledger {ledger.balance(entries)}")
        check(b["balance_paise"] == b["charged_paise"] + b["credits_paise"] + b["paid_paise"] + b["refunded_paise"],
              "balance_components", "student_balance", sid, sid, "components do not add up")
        check(b["balance_paise"] == ledger.identity_balance([totals[sid]], [paid_sum[sid]], [refund_sum[sid]]),
              "balance_identity", "student_balance", sid, sid, "invoices - payments + refunds disagree")
    return n, out


def c6_lifecycle(ix: Index):
    out, n = [], 0
    last: dict[tuple, str] = {}
    for e in ix.ds["event"]:
        key = (e["entity_type"], e["entity_id"])
        n += 1
        if e["entity_type"] in status.TRANSITIONS and e["from_status"] != last.get(key):
            out.append(_v("event_chain", "event", e["event_id"], ix.owner.get(e["entity_id"]),
                          f"from {e['from_status']} but the entity was {last.get(key)}"))
        elif e["entity_type"] in status.TRANSITIONS and not status.is_allowed(e["entity_type"], e["from_status"],
                                                                               e["to_status"]):
            out.append(_v("event_transition", "event", e["event_id"], ix.owner.get(e["entity_id"]),
                          f"{e['from_status']} -> {e['to_status']} is not allowed"))
        last[key] = e["to_status"]
    current = {"enrollment": ("enrollment", "enrollment_id", "status"),
               "invoice": ("invoice", "invoice_id", "status"),
               "payment": ("payment", "payment_id", "status"),
               "scholarship": ("scholarship", "scholarship_id", "status"),
               "refund": ("refund", "refund_id", "status"),
               "eligibility": ("eligibility", "eligibility_id", "decision")}
    for etype, (table, pk, col) in current.items():
        for row in ix.ds[table]:
            n += 1
            state = last.get((etype, row[pk]))
            if state != row[col]:
                out.append(_v("status_replays", table, row[pk], _owner(ix, table, row),
                              f"history ends in {state}, row says {row[col]}"))
    return n, out


def c7_duplicates(ix: Index):
    out, n = [], 0
    by_enrollment = defaultdict(list)
    for i in ix.ds["invoice"]:
        by_enrollment[i["enrollment_id"]].append(i["invoice_id"])
    for eid, invs in by_enrollment.items():
        n += 1
        if len(invs) > 1:
            for dup in sorted(invs)[1:]:
                out.append(_v("one_invoice_per_enrollment", "invoice", dup, ix.owner.get(eid),
                              f"also invoiced as {sorted(invs)[0]}"))
    for table, key in (("scholarship", ("student_id", "term_id")), ("enrollment", ("student_id", "term_id")),
                       ("eligibility", ("student_id", "term_id", "scheme_code")), ("student", ("email",)),
                       ("fee_schedule", ("program_id", "term_id", "fee_type", "applies_to", "effective_from"))):
        pk = schema.TABLES[table].primary_key.columns.keys()[0]
        seen = {}
        for row in ix.ds[table]:
            n += 1
            k = tuple(row[c] for c in key)
            if k in seen:
                out.append(_v("natural_key_unique", table, row[pk], _owner(ix, table, row), f"same {key} as {seen[k]}"))
            seen[k] = row[pk]
    return n, out


def c8_volumes(ix: Index, scale: Scale, gt: list[dict], baseline: bool = False):
    want = {"student": scale.students, "program": scale.programs,
            "invoice": scale.invoices - (scale.duplicates if baseline else 0),
            "scholarship": scale.awards, "payment": scale.payments}
    out = [_v("volume", t, "", None, f"{len(ix.ds[t])} rows, target {w}") for t, w in want.items()
           if len(ix.ds[t]) != w]
    got = Counter(g["issue_type"] for g in gt)
    out += [_v("volume", "ground_truth", k, None, f"{got.get(k, 0)} labels, target {w}")
            for k, w in scale.anomalies.items() if got.get(k, 0) != (0 if baseline else w)]
    return len(want) + len(scale.anomalies), out


def c9_leak(ix: Index, gt: list[dict]):
    out, n = [], 0
    for name in schema.DATA_TABLES:
        for col in schema.columns(name):
            n += 1
            if any(w in col for w in schema.LEAK_WORDS) or col.startswith(schema.LEAK_PREFIXES):
                out.append(_v("leak_column", name, col, None, "column looks like a label"))
    labels = {g["gt_id"] for g in gt}
    for name in schema.DATA_TABLES:
        for row in ix.ds[name]:
            n += 1
            if any(isinstance(v, str) and v in labels for v in row.values()):
                out.append(_v("leak_value", name, "", None, "a ground-truth id appears in an input row"))
    return n, out


# ---------------------------------------------------------------------------------------------- run
def run(ds: Dataset, gt: list[dict], scale: Scale, baseline: bool = False) -> dict:
    """`baseline=True` validates the clean data (no anomalies injected): fewer invoices, no labels."""
    ix = Index(ds)
    raw = {"C1": c1_keys(ix), "C2": c2_foreign_keys(ix), "C3": c3_domain(ix), "C4": c4_dates(ix),
           "C5": c5_arithmetic(ix), "C6": c6_lifecycle(ix), "C7": c7_duplicates(ix),
           "C8": c8_volumes(ix, scale, gt, baseline), "C9": c9_leak(ix, gt)}
    label = {g["student_id"]: g["issue_type"] for g in gt}
    seen_labels: set[str] = set()
    checks, unexpected_total = [], 0
    for cid, name in CHECKS:
        rows, violations = raw[cid]
        expected, unexpected = [], []
        for v in violations:
            issue = label.get(v[3])
            (expected if issue and v[0] in EXPLAINS[issue] else unexpected).append(v)
            if issue and v[0] in EXPLAINS[issue]:
                seen_labels.add(v[3])
        unexpected_total += len(unexpected)
        checks.append({"id": cid, "name": name, "rows_checked": rows, "violations": len(violations),
                       "expected": len(expected), "unexpected": len(unexpected),
                       "rules": dict(sorted(Counter(v[0] for v in violations).items())),
                       "examples": [{"rule": v[0], "table": v[1], "key": v[2], "student": v[3], "message": v[4]}
                                    for v in unexpected[:5]]})
    unseen = sorted(g["gt_id"] for g in gt if g["student_id"] not in seen_labels)
    return {"scale": scale.name, "as_of": AS_OF.isoformat(), "ok": unexpected_total == 0 and not unseen,
            "unexpected_violations": unexpected_total, "labels": len(gt), "labels_without_violation": unseen,
            "rows": {n: len(ds[n]) for n in schema.DATA_TABLES}, "checks": checks}

