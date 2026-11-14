import hashlib
import json

from app.datagen import repro, validate, writer
from app.datagen.generator import DEFAULT_SEED
from app.datagen.scale import SCALES

S = SCALES["starter"]


# ------------------------------------------------------------------------------------------ writer
def test_files_round_trip_exactly(injected, tmp_path):
    ds, gt = injected
    writer.write(ds, gt, tmp_path, "starter", DEFAULT_SEED, ("csv", "json"))
    assert writer.read(tmp_path) == (ds, gt)


def test_gzip_files_read_back_the_same(injected, tmp_path):
    ds, gt = injected
    writer.write(ds, gt, tmp_path, "starter", DEFAULT_SEED, ("csv",), gz=True)
    assert (tmp_path / "student.csv.gz").exists() and not (tmp_path / "student.csv").exists()
    assert writer.read(tmp_path) == (ds, gt)


def test_manifest_checksums_match_the_file_bytes(injected, tmp_path):
    ds, gt = injected
    m = writer.write(ds, gt, tmp_path, "starter", DEFAULT_SEED)
    for name, info in m["tables"].items():
        raw = (tmp_path / f"{name}.csv").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == info["sha256"] and len(raw) == info["bytes"]
        assert raw.count(b"\n") == info["rows"] + 1 and b"\r" not in raw
    assert json.loads((tmp_path / "manifest.json").read_text()) == m


def test_ground_truth_is_only_written_under_its_own_folder(injected, tmp_path):
    ds, gt = injected
    m = writer.write(ds, gt, tmp_path, "starter", DEFAULT_SEED, ("csv", "json"))
    assert (tmp_path / "ground_truth" / "ground_truth.csv").exists()
    assert not [p for p in tmp_path.glob("ground_truth*") if p.is_file()]      # only the folder exists
    assert not list((tmp_path / "json").glob("ground_truth*"))
    assert all("expected_" not in (tmp_path / f"{t}.csv").read_text().splitlines()[0] for t in m["tables"])


def test_manifest_declares_no_external_data(injected, tmp_path):
    m = writer.write(*injected, tmp_path, "starter", DEFAULT_SEED)
    assert m["external_data"]["used"] is False and m["seed"] == DEFAULT_SEED


def test_sql_seed_loads_parents_before_children_and_quotes_text(injected, tmp_path):
    ds, gt = injected
    ds["student"][0] = {**ds["student"][0], "full_name": "O'Brien"}
    writer.write(ds, gt, tmp_path, "starter", DEFAULT_SEED, ("csv", "sql"), sql_dir=tmp_path / "sql")
    sql = (tmp_path / "sql" / "starter.sql").read_text(encoding="utf-8")
    order = [sql.index(f"INSERT INTO {t} ") for t in ("student", "invoice", "invoice_line")]
    assert order == sorted(order)
    assert "'O''Brien'" in sql and "ground_truth" not in sql
    assert "INSERT INTO gt.ground_truth" in (tmp_path / "sql" / "starter_ground_truth.sql").read_text()


# ---------------------------------------------------------------------------------------- validation
def test_clean_data_has_no_violations_at_all(baseline):
    res = validate.run(baseline, [], S, baseline=True)
    assert res["ok"] and all(c["violations"] == 0 for c in res["checks"])
    assert [c["id"] for c in res["checks"]] == [f"C{n}" for n in range(1, 10)]


def test_injected_data_passes_because_every_violation_is_explained_by_a_label(injected):
    ds, gt = injected
    res = validate.run(ds, gt, S)
    assert res["ok"] and res["unexpected_violations"] == 0
    assert res["labels_without_violation"] == []          # the checks can see every labelled case
    assert sum(c["expected"] for c in res["checks"]) > len(gt)


def test_validator_fails_on_an_unlabelled_arithmetic_error(clean):
    inv = clean["invoice"][0]
    inv["total_paise"] += 1
    res = validate.run(clean, [], S, baseline=True)
    bad = [c for c in res["checks"] if c["unexpected"]]
    assert not res["ok"] and bad[0]["id"] == "C5"
    assert bad[0]["examples"][0]["key"] == inv["invoice_id"]


def test_validator_fails_on_a_broken_foreign_key(clean):
    clean["payment"][0]["student_id"] = "STU-999999"
    res = validate.run(clean, [], S, baseline=True)
    assert not res["ok"] and "fk_resolves" in next(c for c in res["checks"] if c["id"] == "C2")["rules"]


def test_validator_fails_on_a_bad_enum_and_a_duplicate_key(clean):
    clean["invoice"][0]["status"] = "LOST"
    clean["payment"].append(dict(clean["payment"][0]))
    rules = {r for c in validate.run(clean, [], S, baseline=True)["checks"] for r in c["rules"]}
    assert {"enum", "pk_unique"} <= rules


def test_validator_fails_on_an_illegal_lifecycle_jump(clean):
    event = next(e for e in clean["event"] if e["entity_type"] == "invoice" and e["to_status"] == "PAID")
    event["from_status"] = "CANCELLED"
    assert not validate.run(clean, [], S, baseline=True)["ok"]


def test_validator_fails_when_a_label_has_no_matching_violation(clean):
    fake = {"gt_id": "GT-000001", "issue_type": "REFUND_EXCEEDS_NET_PAID", "entity_type": "refund",
            "entity_id": "REF-2026-000001", "student_id": clean["student"][0]["student_id"],
            "expected_decision": "BLOCK_REFUND", "expected_value_paise": 0, "details": "nothing was injected"}
    res = validate.run(clean, [fake], S, baseline=True)
    assert not res["ok"] and res["labels_without_violation"] == ["GT-000001"]


def test_validator_fails_when_a_label_leaks_into_an_input_row(clean):
    fake = {"gt_id": "GT-000001", "issue_type": "BALANCE_LEDGER_MISMATCH", "entity_type": "student_balance",
            "entity_id": "x", "student_id": "x", "expected_decision": "RECOMPUTE_BALANCE",
            "expected_value_paise": 0, "details": ""}
    clean["payment"][0]["reference"] = "GT-000001"
    res = validate.run(clean, [fake], S, baseline=True)
    assert "leak_value" in next(c for c in res["checks"] if c["id"] == "C9")["rules"]


def test_wrong_fee_version_is_caught(clean):
    """A FALL invoice billed at the old tuition price is a term-specific fee error."""
    old = next(f for f in clean["fee_schedule"]
               if f["fee_schedule_id"].endswith("FALL-TUITION-V1") and f["effective_to"])
    newer = old["fee_schedule_id"].replace("V1", "V2")
    line = next(ln for ln in clean["invoice_line"] if ln["fee_schedule_id"] == newer)
    line["fee_schedule_id"], line["amount_paise"] = old["fee_schedule_id"], old["amount_paise"]
    res = validate.run(clean, [], S, baseline=True)
    assert "fees_match_schedule" in next(c for c in res["checks"] if c["id"] == "C5")["rules"]


# ---------------------------------------------------------------------------------- reproducibility
def test_two_runs_with_one_seed_are_identical():
    res = repro.check("starter", DEFAULT_SEED)
    assert res["identical"] and all(t["match"] for t in res["tables"].values())
    assert res["total_rows"] == 50_339


def test_a_different_seed_changes_the_checksums():
    a = repro.check("starter", DEFAULT_SEED)["tables"]["payment"]["sha256_run1"]
    b = repro.check("starter", DEFAULT_SEED + 7)["tables"]["payment"]["sha256_run1"]
    assert a != b
