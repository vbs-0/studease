import inspect
from collections import Counter, defaultdict

from app import schema
from app.datagen.scale import SCALES
from app.engine import detect, evaluate

S = SCALES["starter"]


# -------------------------------------------------------------------------------------------- detect
def test_clean_data_produces_no_exceptions(baseline):
    assert detect.run(baseline) == []


def test_every_labelled_case_is_found_and_nothing_else(injected):
    ds, gt = injected
    found = detect.run(ds)
    assert Counter(e["exception_type"] for e in found) == Counter(S.anomalies)
    assert {(e["exception_type"], e["entity_id"]) for e in found} == {(g["issue_type"], g["entity_id"]) for g in gt}


def test_detectors_cannot_see_ground_truth():
    assert list(inspect.signature(detect.run).parameters) == ["ds"]
    for fn in detect.DETECTORS:
        assert list(inspect.signature(fn).parameters) == ["ds"]


def test_exception_rows_match_the_table_and_start_open(injected):
    found = detect.run(injected[0])
    assert all(set(e) == set(schema.columns("exception")) for e in found)
    assert {e["status"] for e in found} == {"OPEN"}
    assert [e["exception_id"] for e in found] == [f"EXC-{n:06d}" for n in range(1, len(found) + 1)]


def test_detection_is_repeatable(injected):
    assert detect.run(injected[0]) == detect.run(injected[0])


def test_boundary_values_are_not_flagged(clean):
    """Exactly equal is allowed: payment fully allocated, award equal to eligible fees, refund equal to net paid."""
    paid = defaultdict(int)
    for a in clean["payment_allocation"]:
        paid[a["payment_id"]] += a["amount_paise"]
    assert any(paid[p["payment_id"]] == p["amount_paise"] for p in clean["payment"])
    s = clean["scholarship"][0]
    s["amount_paise"] = s["eligible_fees_paise"]
    r = clean["refund"][0]
    pays = sum(p["amount_paise"] for p in clean["payment"]
               if p["student_id"] == r["student_id"] and p["received_on"] <= r["approved_on"])
    earlier = sum(x["amount_paise"] for x in clean["refund"] if x["student_id"] == r["student_id"]
                  and (x["approved_on"], x["refund_id"]) < (r["approved_on"], r["refund_id"]))
    r["amount_paise"] = pays - earlier
    assert detect.run(clean) == []


def test_one_cent_over_is_flagged(clean):
    s = clean["scholarship"][0]
    s["amount_paise"] = s["eligible_fees_paise"] + 1
    found = detect.run(clean)
    assert [(e["exception_type"], e["entity_id"]) for e in found] == [("SCHOLARSHIP_EXCEEDS_ELIGIBLE",
                                                                       s["scholarship_id"])]


# ----------------------------------------------------------------------------------------- evaluate
def _label(kind, entity, eid="x"):
    return {"issue_type": kind, "entity_type": entity, "entity_id": eid, "student_id": "s",
            "expected_decision": "BLOCK_REFUND", "expected_value_paise": 100, "details": ""}


def _found(kind, entity, eid, expected=100, found=150, decision="BLOCK_REFUND"):
    return {"exception_type": kind, "entity_type": entity, "entity_id": eid, "student_id": "s",
            "expected_paise": expected, "found_paise": found, "recommended_decision": decision}


def test_precision_and_recall_on_a_hand_built_case():
    """2 true positives, 1 false positive, 1 false negative -> precision 2/3, recall 2/3."""
    k = "REFUND_EXCEEDS_NET_PAID"
    gt = [_label(k, "refund", "a"), _label(k, "refund", "b"), _label(k, "refund", "c")]
    found = [_found(k, "refund", "a"), _found(k, "refund", "b"), _found(k, "refund", "z")]
    d = evaluate.detection(found, gt)["per_type"][k]
    assert (d["true_positives"], d["false_positives"], d["false_negatives"]) == (2, 1, 1)
    assert d["precision"] == d["recall"] == d["f1"] == 0.6667


def test_flagging_everything_gives_full_recall_and_poor_precision():
    k = "REFUND_EXCEEDS_NET_PAID"
    gt = [_label(k, "refund", "a")]
    found = [_found(k, "refund", str(n)) for n in range(9)] + [_found(k, "refund", "a")]
    d = evaluate.detection(found, gt)["per_type"][k]
    assert d["recall"] == 1.0 and d["precision"] == 0.1


def test_a_type_with_no_labels_and_no_reports_has_no_score():
    d = evaluate.detection([], [])
    assert d["overall"]["precision"] is None and d["macro_f1"] is None


def test_decision_and_value_correctness_are_counted_separately():
    k = "REFUND_EXCEEDS_NET_PAID"
    gt = [_label(k, "refund", "a")]
    ok = evaluate.detection([_found(k, "refund", "a")], gt)["per_type"][k]
    wrong = evaluate.detection([_found(k, "refund", "a", expected=7, decision="VOID_DUPLICATE")], gt)["per_type"][k]
    assert (ok["decision_correct"], ok["value_correct"]) == (1, 1)
    assert (wrong["decision_correct"], wrong["value_correct"]) == (0, 0)


def test_perfect_detection_on_the_injected_starter_data(injected):
    ds, gt = injected
    res = evaluate.run(detect.run(ds), gt, ds)
    d = res["detection"]
    assert d["overall"]["precision"] == d["overall"]["recall"] == 1.0 and d["macro_f1"] == 1.0
    assert all(t["decision_correct"] == t["true_positives"] == t["value_correct"] for t in d["per_type"].values())


def test_business_figures_are_consistent_with_each_other(baseline):
    b = evaluate.business(baseline)
    assert b["net_receivable_paise"] == sum(i["total_paise"] for i in baseline["invoice"])
    assert b["billed_paise"] - b["waived_paise"] - b["scholarships_paise"] - b["adjustments_paise"] \
        == b["net_receivable_paise"]
    assert b["outstanding_paise"] - b["credit_held_paise"] == b["net_receivable_paise"] - b["net_collected_paise"]
    assert b["reconciliation_rate"] == 1.0
    assert 0 < b["collection_rate"] < 1 and 0 < b["late_fee_incidence"] < 1
    assert sum(v["awards"] for v in b["awards_by_scheme"].values()) == 750
    assert sum(b["invoice_status"].values()) == b["invoices"]


def test_reconciliation_rate_drops_by_the_number_of_mismatched_students(injected):
    ds, _ = injected
    assert evaluate.business(ds)["reconciliation_rate"] == round(1 - S.anomalies["BALANCE_LEDGER_MISMATCH"] / 500, 4)
