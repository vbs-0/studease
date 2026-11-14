"""Read endpoints: shapes, filters, paging, reconciliation figures and the query budget."""
import pytest
from sqlalchemy import event, text

from app.domain import ledger

pytestmark = pytest.mark.db


def test_students_list_pages_by_keyset_without_gaps_or_repeats(as_role, loaded):
    s = as_role("SUPPORT")
    seen, after = [], None
    while True:
        res = s.get("/students?limit=200" + (f"&after={after}" if after else "")).json()
        seen += [r["student_id"] for r in res["items"]]
        after = res["next"]
        if not after:
            break
    assert seen == sorted(s["student_id"] for s in loaded["ds"]["student"])


def test_students_search_and_filters(as_role, loaded):
    s = as_role("SUPPORT")
    first = loaded["ds"]["student"][0]
    by_name = s.get(f"/students?q={first['full_name'].split()[0]}").json()["items"]
    assert any(r["student_id"] == first["student_id"] for r in by_name)
    assert all(r["balance_paise"] > 0 for r in s.get("/students?owing=true&limit=200").json()["items"])
    flagged = s.get("/students?flagged=true&limit=200").json()["items"]
    assert flagged and all(r["open_exceptions"] > 0 for r in flagged)
    assert s.get("/students?program_id=PRG-01&limit=200").json()["items"][0]["program_id"] == "PRG-01"


def test_student_detail_reconciles_the_three_routes(as_role, loaded):
    s = as_role("SUPPORT")
    labelled = {g["student_id"] for g in loaded["gt"] if g["issue_type"] == "BALANCE_LEDGER_MISMATCH"}
    ok = next(x["student_id"] for x in loaded["ds"]["student"] if x["student_id"] not in labelled)
    bad = next(iter(labelled))
    assert s.get(f"/students/{ok}").json()["balance"]["reconciled"] is True
    mismatch = s.get(f"/students/{bad}").json()["balance"]
    assert mismatch["reconciled"] is False and mismatch["stated"] != mismatch["ledger"]


def test_ledger_has_running_balance_ending_at_the_ledger_sum(as_role, loaded):
    s = as_role("SUPPORT")
    sid = loaded["ds"]["student"][5]["student_id"]
    body = s.get(f"/students/{sid}/ledger").json()
    rows = body["items"]
    assert rows and rows[-1]["running_balance_paise"] == ledger.balance(rows) == body["balance"]["ledger"]


def test_invoice_detail_shows_lines_allocations_and_history(as_role, loaded):
    s = as_role("SUPPORT")
    inv = next(i for i in loaded["ds"]["invoice"] if i["status"] == "PAID")
    body = s.get(f"/invoices/{inv['invoice_id']}").json()
    assert body["invoice"]["total_paise"] == sum(ln["amount_paise"] for ln in body["lines"])
    charges = [ln for ln in body["lines"] if ln["outstanding_paise"] is not None]
    assert charges and all(ln["outstanding_paise"] == 0 for ln in charges)
    assert [h["to_status"] for h in body["history"]][0] == "ISSUED"
    assert s.get("/invoices/INV-NOT-AN-ID").status_code == 404


def test_catalog_endpoints(as_role, loaded):
    s = as_role("ACADEMIC_ADMIN")
    assert len(s.get("/programs").json()["items"]) == 20
    assert len(s.get("/terms").json()["items"]) == 3
    assert len(s.get("/scholarship-schemes").json()["items"]) == len(loaded["ds"]["scholarship_scheme"])
    fees = s.get("/fee-schedules?program_id=PRG-01&term_id=TERM-2026-FALL").json()["items"]
    assert fees and {f["program_id"] for f in fees} == {"PRG-01"}
    awards = s.get("/scholarships?limit=200").json()
    assert len(awards["items"]) == 200 and awards["next"]
    assert s.get("/eligibility?decision=INELIGIBLE&limit=5").json()["items"][0]["decision"] == "INELIGIBLE"


def test_overview_adds_up(as_role, loaded):
    body = as_role("SUPPORT").get("/metrics/overview").json()
    assert body["students"] == len(loaded["ds"]["student"]) and body["invoices"] == len(loaded["ds"]["invoice"])
    assert sum(body["invoice_status"].values()) == body["invoices"]
    assert body["open_exceptions"] == sum(body["open_by_type"].values()) > 0
    stated = sum(b["balance_paise"] for b in loaded["ds"]["student_balance"])
    assert body["owed_paise"] - body["credit_held_paise"] == stated


def test_exceptions_queue_filters_and_counts(as_role, loaded):
    s = as_role("SUPPORT")
    body = s.get("/exceptions?status=OPEN&limit=200").json()
    assert sum(body["counts"].values()) == len(body["items"]) == sum(1 for _ in body["items"])
    one = s.get("/exceptions?exception_type=DUPLICATE_INVOICE&limit=200").json()["items"]
    assert one and {e["exception_type"] for e in one} == {"DUPLICATE_INVOICE"}


def test_quality_is_for_platform_admins_only(as_role, loaded):
    assert as_role("SUPPORT").get("/quality").status_code == 403
    body = as_role("PLATFORM_ADMIN").get("/quality").json()
    assert body["scale"] == "starter" and body["validation"]["ok"] is True and body["repro"]["identical"] is True


def test_health_endpoints_are_public(client, loaded):
    assert client.get("/api/v1/healthz").json() == {"status": "ok"}
    assert client.get("/api/v1/readyz").json() == {"status": "ready"}


def test_endpoints_run_a_constant_number_of_queries(as_role, loaded):
    """No N+1: a student with many ledger rows costs the same number of statements as one with few."""
    s = as_role("SUPPORT")
    counts = []
    engine = loaded["engine"]

    def counter(*_a):
        counts[-1] += 1
    event.listen(engine, "before_cursor_execute", counter)
    try:
        for sid in (loaded["ds"]["student"][1]["student_id"], loaded["ds"]["student"][400]["student_id"]):
            for path in (f"/students/{sid}", f"/students/{sid}/ledger", f"/students/{sid}/events"):
                counts.append(0)
                assert s.get(path).status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", counter)
    assert counts[:3] == counts[3:] and max(counts) <= 8, counts
    with engine.connect() as c:                                   # sanity: the fixture really has data
        assert c.execute(text("SELECT count(*) FROM ledger_entry")).scalar() > 1000
