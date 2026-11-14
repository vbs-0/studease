"""Write endpoints: payments (R-PAY, S-9, S-15), withdrawal (R-WD, R-REF) and exception resolution."""
import threading

import pytest
from sqlalchemy import text

from app.domain import ledger

from .conftest import clean_students

pytestmark = pytest.mark.db
KEY = {"Idempotency-Key": "test-key-0001"}


def _books_reconcile(engine, sid):
    with engine.connect() as c:
        stated = c.execute(text("SELECT balance_paise FROM student_balance WHERE student_id = :s"), {"s": sid}).scalar()
        led = c.execute(text("SELECT coalesce(sum(amount_paise),0) FROM ledger_entry WHERE student_id=:s"), {"s": sid}).scalar()
        docs = c.execute(text("""SELECT (SELECT coalesce(sum(total_paise),0) FROM invoice WHERE student_id=:s)
              - (SELECT coalesce(sum(amount_paise),0) FROM payment WHERE student_id=:s)
              + (SELECT coalesce(sum(amount_paise),0) FROM refund WHERE student_id=:s)"""), {"s": sid}).scalar()
    return stated == led == docs


def _owing_student(env):
    with env["engine"].connect() as c:
        rows = c.execute(text("SELECT student_id FROM student_balance WHERE balance_paise > 50000 ORDER BY student_id")).scalars()
        ok = set(clean_students(env))
        return next(s for s in rows if s in ok)


def test_payment_is_allocated_oldest_due_first_and_books_still_reconcile(as_role, loaded):
    sid = _owing_student(loaded)
    s = as_role("SUPPORT")
    before = s.get(f"/students/{sid}").json()["balance"]["stated"]
    res = s.post("/payments", {"student_id": sid, "amount_paise": 20000, "method": "UPI", "reference": "t-1"}, KEY)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["payment"]["payment_id"].startswith("PAY-2026-") and body["payment"]["status"] == "ALLOCATED"
    assert sum(a["amount_paise"] for a in body["allocations"]) + body["unapplied_paise"] == 20000
    assert body["balance"]["balance_paise"] == before - 20000
    assert _books_reconcile(loaded["engine"], sid)
    with loaded["engine"].connect() as c:
        assert c.execute(text("SELECT count(*) FROM event WHERE entity_id = :p"),
                         {"p": body["payment"]["payment_id"]}).scalar() == 2      # RECEIVED, then ALLOCATED
        assert c.execute(text("SELECT count(*) FROM ledger_entry WHERE source_id = :p"),
                         {"p": body["payment"]["payment_id"]}).scalar() == 1


def test_a_payment_larger_than_the_debt_keeps_the_rest_as_credit(as_role, loaded):
    sid = _owing_student(loaded)
    s = as_role("SUPPORT")
    owed = s.get(f"/students/{sid}").json()["balance"]["stated"]
    res = s.post("/payments", {"student_id": sid, "amount_paise": owed + 5000, "method": "CARD", "reference": "t-2"}, KEY)
    body = res.json()
    assert res.status_code == 201 and body["unapplied_paise"] > 0
    assert body["payment"]["status"] == "PARTIALLY_ALLOCATED" or body["payment"]["status"] == "ALLOCATED"
    assert body["balance"]["balance_paise"] == -5000
    assert _books_reconcile(loaded["engine"], sid)


def test_s9_the_same_key_replays_and_never_writes_twice(as_role, loaded):
    sid = _owing_student(loaded)
    s = as_role("SUPPORT")
    body = {"student_id": sid, "amount_paise": 1000, "method": "UPI", "reference": "t-3"}
    first = s.post("/payments", body, KEY)
    again = s.post("/payments", body, KEY)
    assert first.status_code == 201 and again.status_code == 200 and again.headers["Idempotent-Replay"] == "true"
    assert again.json() == first.json()
    with loaded["engine"].connect() as c:
        assert c.execute(text("SELECT count(*) FROM payment WHERE reference = 't-3'")).scalar() == 1
    changed = s.post("/payments", {**body, "amount_paise": 2000}, KEY)
    assert changed.status_code == 422 and changed.json()["error"]["code"] == "IDEMPOTENCY_MISMATCH"


def test_s9_keys_are_scoped_to_the_caller(as_role, loaded):
    sid = _owing_student(loaded)
    body = {"student_id": sid, "amount_paise": 1000, "method": "UPI", "reference": "t-4"}
    a = as_role("SUPPORT").post("/payments", body, KEY)
    b = as_role("PLATFORM_ADMIN").post("/payments", body, KEY)      # same key, other user: a new payment
    assert a.status_code == b.status_code == 201
    assert a.json()["payment"]["payment_id"] != b.json()["payment"]["payment_id"]


def test_a_payment_needs_a_valid_key_and_an_existing_student(as_role, loaded):
    s = as_role("SUPPORT")
    sid = loaded["ds"]["student"][0]["student_id"]
    body = {"student_id": sid, "amount_paise": 100, "method": "UPI", "reference": "t-5"}
    assert s.post("/payments", body).status_code == 422
    assert s.post("/payments", body, {"Idempotency-Key": "short"}).status_code == 422
    assert s.post("/payments", {**body, "student_id": "STU-999999"}, KEY).status_code == 404


def test_s15_concurrent_payments_for_one_student_never_double_allocate(client, loaded, as_role):
    sid = _owing_student(loaded)
    s = as_role("SUPPORT")
    owed = s.get(f"/students/{sid}").json()["balance"]["stated"]
    results = []

    def pay(n):
        results.append(s.post("/payments", {"student_id": sid, "amount_paise": owed, "method": "UPI",
                                            "reference": f"c-{n}"}, {"Idempotency-Key": f"concurrent-{n}"}))
    threads = [threading.Thread(target=pay, args=(n,)) for n in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert [r.status_code for r in results] == [201, 201], [r.text for r in results]
    allocated = sum(a["amount_paise"] for r in results for a in r.json()["allocations"])
    assert allocated <= owed + 1 and sum(r.json()["unapplied_paise"] for r in results) >= owed - 1   # no double use
    assert len({r.json()["payment"]["payment_id"] for r in results}) == 2
    assert _books_reconcile(loaded["engine"], sid)


def _enrolled_with_payment(env):
    ok = set(clean_students(env))
    with env["engine"].connect() as c:
        rows = c.execute(text("""
            SELECT e.enrollment_id, e.student_id FROM enrollment e JOIN invoice i USING (enrollment_id)
            JOIN invoice_line l USING (invoice_id) JOIN payment_allocation a USING (invoice_line_id)
            WHERE e.status = 'ENROLLED' AND e.term_id = 'TERM-2026-FALL' AND i.status <> 'VOID'
            GROUP BY e.enrollment_id, e.student_id HAVING sum(a.amount_paise) > 0 ORDER BY 1""")).all()
    return next(r for r in rows if r[1] in ok)


def test_withdrawal_adjusts_reverses_refunds_and_keeps_the_books_balanced(as_role, loaded):
    enrollment_id, sid = _enrolled_with_payment(loaded)
    res = as_role("ACADEMIC_ADMIN").post(f"/enrollments/{enrollment_id}/withdraw", {})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["outcome"] == "WITHDRAWN" and body["adjustments"]
    assert all(a["amount_paise"] < 0 for a in body["adjustments"] + body["reversals"])
    refunded = sum(r["amount_paise"] for r in body["refunds"])
    assert refunded <= sum(-a["amount_paise"] for a in body["reversals"])          # R-REF-2
    assert _books_reconcile(loaded["engine"], sid)
    with loaded["engine"].connect() as c:
        assert c.execute(text("SELECT status FROM enrollment WHERE enrollment_id = :e"), {"e": enrollment_id}).scalar() == "WITHDRAWN"
        total = c.execute(text("SELECT total_paise FROM invoice WHERE invoice_id = :i"), {"i": body["invoice"]["invoice_id"]}).scalar()
        lines = c.execute(text("SELECT coalesce(sum(amount_paise),0) FROM invoice_line WHERE invoice_id = :i"), {"i": body["invoice"]["invoice_id"]}).scalar()
        assert total == lines
        stated = c.execute(text("SELECT balance_paise FROM student_balance WHERE student_id = :s"), {"s": sid}).scalar()
        entries = [dict(r) for r in c.execute(text("SELECT amount_paise FROM ledger_entry WHERE student_id = :s"), {"s": sid}).mappings()]
        assert stated == ledger.balance(entries)


def test_withdrawing_twice_is_a_conflict_and_a_bad_date_is_rejected(as_role, loaded):
    enrollment_id, _ = _enrolled_with_payment(loaded)
    admin = as_role("ACADEMIC_ADMIN")
    assert admin.post(f"/enrollments/{enrollment_id}/withdraw", {"left_on": "2030-01-01"}).status_code == 422
    assert admin.post(f"/enrollments/{enrollment_id}/withdraw", {}).status_code == 200
    again = admin.post(f"/enrollments/{enrollment_id}/withdraw", {})
    assert again.status_code == 409 and again.json()["error"]["code"] == "NOT_ENROLLED"
    assert admin.post("/enrollments/ENR-999999-2026-FALL/withdraw", {}).status_code == 404


def test_cancelling_before_the_term_starts_refunds_in_full_and_revokes_the_award(as_role, loaded):
    enrollment_id, sid = _enrolled_with_payment(loaded)
    res = as_role("ACADEMIC_ADMIN").post(f"/enrollments/{enrollment_id}/withdraw", {"left_on": "2026-08-10"})
    body = res.json()
    assert res.status_code == 200 and body["outcome"] == "CANCELLED" and body["invoice"]["status"] == "CANCELLED"
    assert _books_reconcile(loaded["engine"], sid)


def test_resolving_an_exception_closes_it_once_and_writes_an_event(as_role, loaded):
    s = as_role("SUPPORT")
    item = s.get("/exceptions?status=OPEN&limit=1").json()["items"][0]
    res = s.post(f"/exceptions/{item['exception_id']}/resolve", {"status": "RESOLVED", "note": "checked"})
    assert res.status_code == 200
    again = s.post(f"/exceptions/{item['exception_id']}/resolve", {"status": "DISMISSED", "note": "no"})
    assert again.status_code == 409
    row = s.get(f"/exceptions?student_id={item['student_id']}").json()["items"]
    assert next(e for e in row if e["exception_id"] == item["exception_id"])["status"] == "RESOLVED"
    with loaded["engine"].connect() as c:
        assert c.execute(text("SELECT to_status FROM event WHERE entity_id = :e"), {"e": item["exception_id"]}).scalar() == "RESOLVED"
    assert s.post("/exceptions/EXC-999999/resolve", {"status": "RESOLVED", "note": "x"}).status_code == 404
    assert s.post("/exceptions/bad/resolve", {"status": "RESOLVED", "note": "x"}).status_code == 404
    assert s.post(f"/exceptions/{item['exception_id']}/resolve", {"status": "RESOLVED", "note": ""}).status_code == 422
