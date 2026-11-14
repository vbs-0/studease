from collections import Counter, defaultdict
from datetime import date

from app import schema
from app.datagen.generator import DEFAULT_SEED, generate
from app.datagen.scale import SCALES
from app.domain import ledger
from app.domain.billing import outstanding_by_line
from app.domain.calendar import AS_OF, TERMS
from app.domain.status import is_allowed
from app.domain.withdrawal import refund_share_bp

S = SCALES["starter"]


def test_exact_volumes_after_injection(injected):
    ds, _ = injected
    assert len(ds["student"]) == S.students == 500
    assert len(ds["program"]) == S.programs == 20
    assert len(ds["invoice"]) == S.invoices == 1_500
    assert len(ds["scholarship"]) == S.awards == 750
    assert len(ds["payment"]) == S.payments == 2_500


def test_baseline_is_a_third_term_short_only_by_the_duplicates(baseline):
    assert len(baseline["invoice"]) == S.invoices - S.duplicates


def test_same_seed_gives_identical_data_and_another_seed_does_not():
    a, _ = generate("starter", DEFAULT_SEED)
    b, _ = generate("starter", DEFAULT_SEED)
    c, _ = generate("starter", DEFAULT_SEED + 1)
    assert a == b
    assert a["payment"] != c["payment"]


def test_every_row_has_exactly_the_columns_of_its_table(injected):
    ds, _ = injected
    for name in schema.DATA_TABLES:
        cols = set(schema.columns(name))
        assert all(set(row) == cols for row in ds[name]), name


def test_coverage_of_the_cases_the_brief_asks_for(baseline):
    ds = baseline
    pay = Counter(p["status"] for p in ds["payment"])
    assert pay["PARTIALLY_ALLOCATED"] > 0                                   # overpayment left as credit
    assert any(r["reason"] == "OVERPAYMENT" for r in ds["refund"])          # unused credit refunded
    inv = Counter(i["status"] for i in ds["invoice"])
    assert all(inv[s] > 0 for s in ("ISSUED", "PARTIALLY_PAID", "PAID", "OVERDUE", "CANCELLED"))
    assert {s["waiver_type"] for s in ds["student"]} >= {"STAFF_WARD", "SIBLING", "HARDSHIP"}
    waivers = Counter(ln["description"].split()[1] for ln in ds["invoice_line"] if ln["line_type"] == "WAIVER")
    assert set(waivers) == {"STAFF_WARD", "SIBLING", "HARDSHIP"}            # fee waivers of every kind
    assert any(ln["line_type"] == "LATE_FEE" for ln in ds["invoice_line"])
    assert any(ln["fee_schedule_id"] and ln["fee_schedule_id"].endswith("-V2") for ln in ds["invoice_line"])
    assert not any(ln["fee_schedule_id"] and ln["fee_schedule_id"].endswith("TUITION-V1")
                   and "FALL" in ln["fee_schedule_id"] and ln["posted_on"] == TERMS["FALL"].issue
                   and ln["fee_schedule_id"] in {f["fee_schedule_id"] for f in ds["fee_schedule"] if f["effective_to"]}
                   for ln in ds["invoice_line"])                            # a FALL invoice never bills the old price


def test_withdrawals_cover_every_refund_band(baseline):
    bands = Counter()
    for e in baseline["enrollment"]:
        if e["status"] == "WITHDRAWN":
            bands[refund_share_bp(e["left_on"], next(t for t in TERMS.values() if t.term_id == e["term_id"]))] += 1
        elif e["status"] == "CANCELLED":
            bands["cancelled"] += 1
    assert set(bands) == {"cancelled", 7500, 5000, 0}, bands


def test_invoice_total_is_the_sum_of_its_lines(baseline):
    total = defaultdict(int)
    for ln in baseline["invoice_line"]:
        total[ln["invoice_id"]] += ln["amount_paise"]
    assert all(i["total_paise"] == total[i["invoice_id"]] for i in baseline["invoice"])


def test_no_payment_or_line_is_over_allocated(baseline):
    paid = defaultdict(int)
    for a in baseline["payment_allocation"]:
        paid[a["payment_id"]] += a["amount_paise"]
    assert all(paid[p["payment_id"]] <= p["amount_paise"] for p in baseline["payment"])
    by_inv = defaultdict(list)
    for ln in baseline["invoice_line"]:
        by_inv[ln["invoice_id"]].append(ln)
    per_line = defaultdict(list)
    for a in baseline["payment_allocation"]:
        per_line[a["invoice_line_id"]].append(a)
    for lines in by_inv.values():
        allocs = [a for ln in lines for a in per_line[ln["invoice_line_id"]]]
        assert all(v >= 0 for v in outstanding_by_line(lines, allocs).values())


def test_balance_reconciles_three_ways(baseline):
    led = defaultdict(int)
    for e in baseline["ledger_entry"]:
        led[e["student_id"]] += e["amount_paise"]
    ident = defaultdict(int)
    for i in baseline["invoice"]:
        ident[i["student_id"]] += i["total_paise"]
    for p in baseline["payment"]:
        ident[p["student_id"]] -= p["amount_paise"]
    for r in baseline["refund"]:
        ident[r["student_id"]] += r["amount_paise"]
    for b in baseline["student_balance"]:
        sid = b["student_id"]
        assert b["balance_paise"] == led[sid] == ident[sid]
        assert b["balance_paise"] == b["charged_paise"] + b["credits_paise"] + b["paid_paise"] + b["refunded_paise"]
    assert ledger.balance(baseline["ledger_entry"]) == sum(b["balance_paise"] for b in baseline["student_balance"])


def test_awards_never_exceed_eligible_fees_and_are_one_per_student_and_term(baseline):
    assert all(0 < s["amount_paise"] <= s["eligible_fees_paise"] for s in baseline["scholarship"])
    keys = Counter((s["student_id"], s["term_id"]) for s in baseline["scholarship"])
    assert max(keys.values()) == 1
    elig = {e["eligibility_id"]: e for e in baseline["eligibility"]}
    assert all(elig[s["eligibility_id"]]["decision"] == "ELIGIBLE" for s in baseline["scholarship"])


def test_scholarship_credit_lines_add_up_to_the_award(baseline):
    credit = defaultdict(int)
    for ln in baseline["invoice_line"]:
        if ln["line_type"] == "SCHOLARSHIP":
            credit[ln["scholarship_id"]] -= ln["amount_paise"]
    assert all(credit[s["scholarship_id"]] == s["amount_paise"] for s in baseline["scholarship"])


def test_event_history_follows_the_lifecycle(baseline):
    last = {}
    for e in baseline["event"]:
        key = (e["entity_type"], e["entity_id"])
        assert e["from_status"] == last.get(key), e
        assert is_allowed(e["entity_type"], e["from_status"], e["to_status"]), e
        last[key] = e["to_status"]
    status_of = {"invoice": {i["invoice_id"]: i["status"] for i in baseline["invoice"]},
                 "payment": {p["payment_id"]: p["status"] for p in baseline["payment"]},
                 "enrollment": {e["enrollment_id"]: e["status"] for e in baseline["enrollment"]}}
    for (etype, eid), state in last.items():
        if etype in status_of:
            assert status_of[etype][eid] == state, (etype, eid)


def test_nothing_is_dated_after_the_as_of_date(baseline):
    for p in baseline["payment"]:
        assert p["received_on"] <= AS_OF
    for e in baseline["event"]:
        assert e["occurred_on"] <= TERMS["FALL"].end
    assert all(e["occurred_on"] >= date(2025, 1, 1) for e in baseline["event"])
