from collections import Counter, defaultdict

from app.datagen.scale import SCALES

S = SCALES["starter"]
STUDENT_TABLES = ("student", "enrollment", "invoice", "scholarship", "payment", "refund", "ledger_entry",
                  "student_balance", "eligibility")


def test_one_label_per_injected_case_with_the_scale_counts(injected):
    _, gt = injected
    assert Counter(g["issue_type"] for g in gt) == Counter(S.anomalies)
    assert [g["gt_id"] for g in gt] == [f"GT-{n:06d}" for n in range(1, len(gt) + 1)]


def test_each_case_is_on_its_own_student(injected):
    _, gt = injected
    students = [g["student_id"] for g in gt]
    assert len(students) == len(set(students)) == sum(S.anomalies.values())


def test_every_label_points_at_an_existing_row(injected):
    ds, gt = injected
    key = {"payment": "payment_id", "scholarship": "scholarship_id", "invoice": "invoice_id",
           "refund": "refund_id", "student_balance": "student_id"}
    for g in gt:
        assert any(row[key[g["entity_type"]]] == g["entity_id"] for row in ds[g["entity_type"]]), g


def test_students_without_a_label_are_byte_identical_to_the_baseline(baseline, injected):
    ds, gt = injected
    touched = {g["student_id"] for g in gt}
    for name in STUDENT_TABLES:
        mine = [r for r in baseline[name] if r["student_id"] not in touched]
        theirs = [r for r in ds[name] if r["student_id"] not in touched]
        assert mine == theirs, name
    inv_owner = {i["invoice_id"]: i["student_id"] for i in ds["invoice"]}
    base_lines = [ln for ln in baseline["invoice_line"] if inv_owner[ln["invoice_id"]] not in touched]
    new_lines = [ln for ln in ds["invoice_line"] if inv_owner[ln["invoice_id"]] not in touched]
    assert base_lines == new_lines
    for name in ("program", "term", "fee_schedule", "scholarship_scheme"):
        assert baseline[name] == ds[name]


def test_labels_are_not_visible_in_any_input_table(injected):
    ds, gt = injected
    labelled_ids = {g["gt_id"] for g in gt}
    for name, rows in ds.items():
        for row in rows:
            assert not (set(map(str, row.values())) & labelled_ids), name
            assert not any(k.startswith("expected_") or k in ("issue_type", "anomaly") for k in row), name


def test_allocation_anomaly_pushes_the_payment_over_its_amount(injected):
    ds, gt = injected
    paid = defaultdict(int)
    for a in ds["payment_allocation"]:
        paid[a["payment_id"]] += a["amount_paise"]
    amount = {p["payment_id"]: p["amount_paise"] for p in ds["payment"]}
    for g in (g for g in gt if g["issue_type"] == "ALLOC_EXCEEDS_PAYMENT"):
        assert paid[g["entity_id"]] - amount[g["entity_id"]] == g["expected_value_paise"] > 0


def test_scholarship_anomaly_exceeds_the_eligible_fees(injected):
    ds, gt = injected
    by_id = {s["scholarship_id"]: s for s in ds["scholarship"]}
    for g in (g for g in gt if g["issue_type"] == "SCHOLARSHIP_EXCEEDS_ELIGIBLE"):
        s = by_id[g["entity_id"]]
        assert s["amount_paise"] > s["eligible_fees_paise"] == g["expected_value_paise"]


def test_duplicate_invoice_repeats_an_enrollment_and_its_fee_lines(injected):
    ds, gt = injected
    inv = {i["invoice_id"]: i for i in ds["invoice"]}
    lines = defaultdict(list)
    for ln in ds["invoice_line"]:
        lines[ln["invoice_id"]].append(ln)
    for g in (g for g in gt if g["issue_type"] == "DUPLICATE_INVOICE"):
        dup = inv[g["entity_id"]]
        twins = [i for i in ds["invoice"] if i["enrollment_id"] == dup["enrollment_id"]]
        assert len(twins) == 2
        first = next(i for i in twins if i["invoice_id"] != dup["invoice_id"])
        fees = lambda i: sorted((ln["fee_schedule_id"], ln["amount_paise"])  # noqa: E731
                                for ln in lines[i["invoice_id"]] if ln["line_type"] == "FEE")
        assert fees(dup) == fees(first)
        assert dup["total_paise"] == sum(ln["amount_paise"] for ln in lines[dup["invoice_id"]])


def test_refund_anomaly_exceeds_what_the_student_has_net_paid(injected):
    ds, gt = injected
    paid, refunded = defaultdict(int), defaultdict(int)
    for p in ds["payment"]:
        paid[p["student_id"]] += p["amount_paise"]
    for r in ds["refund"]:
        refunded[r["student_id"]] += r["amount_paise"]
    amount = {r["refund_id"]: r["amount_paise"] for r in ds["refund"]}
    for g in (g for g in gt if g["issue_type"] == "REFUND_EXCEEDS_NET_PAID"):
        sid, injected_amount = g["student_id"], amount[g["entity_id"]]
        net_before = paid[sid] - (refunded[sid] - injected_amount)   # payments minus the earlier, legitimate refunds
        assert injected_amount > g["expected_value_paise"] == net_before


def test_balance_anomaly_moves_the_stated_balance_away_from_the_ledger(injected):
    ds, gt = injected
    led = defaultdict(int)
    for e in ds["ledger_entry"]:
        led[e["student_id"]] += e["amount_paise"]
    stated = {b["student_id"]: b["balance_paise"] for b in ds["student_balance"]}
    for g in (g for g in gt if g["issue_type"] == "BALANCE_LEDGER_MISMATCH"):
        assert led[g["student_id"]] == g["expected_value_paise"] != stated[g["student_id"]]
