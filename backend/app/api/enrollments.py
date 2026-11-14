"""Withdraw or cancel an enrollment: R-WD adjustment, de-allocation of what is now overpaid, R-REF refund."""
from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app import ids
from app.api import learner, txn
from app.api.deps import Conn, CurrentUser, check_id, require_role
from app.api.errors import ApiError
from app.domain import ledger, status
from app.domain.billing import outstanding_by_line
from app.domain.calendar import AS_OF, term_of
from app.domain.withdrawal import (
    adjustment_lines,
    classify,
    excess_by_line,
    plan_reversals,
    refund_due,
    refund_share_bp,
)

router = APIRouter(tags=["enrollments"])


class Withdraw(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left_on: date | None = None           # defaults to the data as-of date


@router.post("/enrollments/{enrollment_id}/withdraw", dependencies=[require_role("ACADEMIC_ADMIN", "PLATFORM_ADMIN")])
def withdraw(enrollment_id: str, body: Withdraw, conn: Conn, user: CurrentUser):
    return do_withdraw(enrollment_id, body, conn, user)


@router.post("/me/enrollments/{enrollment_id}/withdraw", dependencies=[require_role("LEARNER")])
def withdraw_own(enrollment_id: str, body: Withdraw, conn: Conn, user: CurrentUser):
    check_id("enrollment", enrollment_id)
    owner = conn.execute(text("SELECT student_id FROM enrollment WHERE enrollment_id = :e"), {"e": enrollment_id}).scalar()
    if owner != user.student_id:                       # someone else's enrollment looks exactly like a missing one
        raise ApiError(404, "NOT_FOUND", "No such enrollment.")
    return do_withdraw(enrollment_id, body, conn, user)


def do_withdraw(enrollment_id: str, body: Withdraw, conn, user: CurrentUser):
    check_id("enrollment", enrollment_id)
    enr = conn.execute(text("SELECT * FROM enrollment WHERE enrollment_id = :e"),
                       {"e": enrollment_id}).mappings().first()
    if enr is None:
        raise ApiError(404, "NOT_FOUND", "No such enrollment.")
    sid = enr["student_id"]
    txn.lock_student(conn, sid)
    c = txn.begin_write(conn)
    enr = conn.execute(text("SELECT * FROM enrollment WHERE enrollment_id = :e"), {"e": enrollment_id}).mappings().one()
    if enr["status"] != "ENROLLED":                                   # re-read under the lock
        raise ApiError(409, "NOT_ENROLLED", f"This enrollment is already {enr['status']}.")
    term = term_of(enr["term_id"])
    left_on = body.left_on or AS_OF
    if not (enr["enrolled_on"] <= left_on <= AS_OF):
        raise ApiError(422, "BAD_DATE", f"left_on must be between {enr['enrolled_on']} and {AS_OF}.")
    kind = classify(left_on, term)                                    # R-WD-1
    actor = user.app_user_id

    invoice = conn.execute(text("SELECT * FROM invoice WHERE enrollment_id = :e AND status <> 'VOID'"
                                " ORDER BY invoice_id LIMIT 1"), {"e": enrollment_id}).mappings().first()
    out = {"enrollment_id": enrollment_id, "outcome": kind, "adjustments": [], "reversals": [], "refunds": []}
    if invoice:
        inv_id = invoice["invoice_id"]
        _, lines, allocs = txn.student_documents(conn, sid)
        inv_lines = [ln for ln in lines if ln["invoice_id"] == inv_id]
        line_ids = {ln["invoice_line_id"] for ln in inv_lines}
        inv_allocs = [a for a in allocs if a["invoice_line_id"] in line_ids]
        adj = adjustment_lines(inv_id, inv_lines, refund_share_bp(left_on, term), len(inv_lines) + 1, left_on)
        for ln in adj:
            txn.insert_row(conn, "invoice_line", ln)
            txn.add_ledger(conn, c, ledger.entry_for_line(sid, ln))
        all_lines = inv_lines + adj
        per_payment_count: dict[str, int] = {}
        for a in allocs:
            per_payment_count[a["payment_id"]] = per_payment_count.get(a["payment_id"], 0) + 1
        returned: dict[str, int] = {}
        new_allocs = []
        for pid, line_id, amount in plan_reversals(inv_allocs, excess_by_line(all_lines, inv_allocs)):
            per_payment_count[pid] = per_payment_count.get(pid, 0) + 1
            row = {"allocation_id": ids.allocation_id(pid, per_payment_count[pid]), "payment_id": pid,
                   "invoice_line_id": line_id, "amount_paise": -amount, "allocated_on": left_on}
            txn.insert_row(conn, "payment_allocation", row)
            new_allocs.append(row)
            returned[pid] = returned.get(pid, 0) + amount
        paid = conn.execute(text("SELECT coalesce(sum(amount_paise), 0) FROM payment WHERE student_id = :s"),
                            {"s": sid}).scalar()
        refunded = conn.execute(text("SELECT coalesce(sum(amount_paise), 0) FROM refund WHERE student_id = :s"),
                                {"s": sid}).scalar()
        budget = refund_due(sum(returned.values()), paid - refunded)  # R-REF-2
        new_refunds: dict[str, int] = {}
        for pid, amount in returned.items():
            give = min(amount, budget)
            if give <= 0:
                continue
            refund = {"refund_id": ids.refund_id(c.take("refund")), "student_id": sid, "invoice_id": inv_id,
                      "payment_id": pid, "amount_paise": give, "reason": "CANCELLATION" if kind == "CANCELLED"
                      else "WITHDRAWAL", "status": "APPROVED", "approved_on": left_on, "paid_on": None}
            txn.insert_row(conn, "refund", refund)
            txn.add_ledger(conn, c, ledger.entry_for_refund(refund))
            txn.add_event(conn, c, "refund", refund["refund_id"], None, "APPROVED", left_on, actor)
            out["refunds"].append(refund)
            new_refunds[pid] = give
            budget -= give
        for pid in returned:                                           # payment status follows what was returned
            row = conn.execute(text("SELECT status, amount_paise FROM payment WHERE payment_id = :p"),
                               {"p": pid}).mappings().one()
            applied = conn.execute(text("SELECT coalesce(sum(amount_paise), 0) FROM payment_allocation"
                                        " WHERE payment_id = :p"), {"p": pid}).scalar()
            back = conn.execute(text("SELECT coalesce(sum(amount_paise), 0) FROM refund WHERE payment_id = :p"),
                                {"p": pid}).scalar()
            now = status.payment_status(row["amount_paise"], applied, back)
            if now == "RECEIVED" and row["status"] != "RECEIVED":
                now = "PARTIALLY_ALLOCATED"
            if now != row["status"] and status.is_allowed("payment", row["status"], now):
                conn.execute(text("UPDATE payment SET status = :s WHERE payment_id = :p"), {"s": now, "p": pid})
                txn.add_event(conn, c, "payment", pid, row["status"], now, left_on, actor)
        mine = inv_allocs + new_allocs
        owed = sum(outstanding_by_line(all_lines, mine).values())
        total = sum(ln["amount_paise"] for ln in all_lines)
        new_status = status.invoice_status(False, kind == "CANCELLED", owed, sum(a["amount_paise"] for a in mine),
                                           invoice["due_date"], AS_OF)
        conn.execute(text("UPDATE invoice SET total_paise = :t, status = :s WHERE invoice_id = :i"),
                     {"t": total, "s": new_status, "i": inv_id})
        if new_status != invoice["status"] and status.is_allowed("invoice", invoice["status"], new_status):
            txn.add_event(conn, c, "invoice", inv_id, invoice["status"], new_status, left_on, actor)
        if kind == "CANCELLED":                                        # the award goes with the cancelled invoice
            for sch in conn.execute(text("SELECT scholarship_id, status FROM scholarship WHERE invoice_id = :i"
                                         " AND status <> 'REVOKED'"), {"i": inv_id}).mappings().all():
                conn.execute(text("UPDATE scholarship SET status = 'REVOKED' WHERE scholarship_id = :s"),
                             {"s": sch["scholarship_id"]})
                txn.add_event(conn, c, "scholarship", sch["scholarship_id"], sch["status"], "REVOKED", left_on, actor)
        out["adjustments"] = adj
        out["reversals"] = new_allocs
        out["invoice"] = {"invoice_id": inv_id, "status": new_status, "total_paise": total}

    conn.execute(text("UPDATE enrollment SET status = :s, left_on = :d WHERE enrollment_id = :e"),
                 {"s": kind, "d": left_on, "e": enrollment_id})
    txn.add_event(conn, c, "enrollment", enrollment_id, "ENROLLED", kind, left_on, actor)
    out["balance"] = txn.refresh_balance(conn, sid, AS_OF)
    conn.commit()
    return out


@router.post("/students/{student_id}/enroll", status_code=201,
             dependencies=[require_role("ACADEMIC_ADMIN", "SUPPORT", "PLATFORM_ADMIN")])
def enroll_for(student_id: str, body: learner.Enroll, conn: Conn, user: CurrentUser):
    check_id("student", student_id)
    if conn.execute(text("SELECT 1 FROM student WHERE student_id = :s"), {"s": student_id}).first() is None:
        raise ApiError(404, "NOT_FOUND", "No such student.")
    return learner.enroll_student(conn, student_id, body.term_id, list(dict.fromkeys(body.applications)), user.app_user_id)
