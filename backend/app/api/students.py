"""Students: search, profile, ledger, state history and invoices. Money is hidden from instructors (spec section 3)."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.api.deps import FINANCE, STAFF, Conn, CurrentUser, Page, check_id, require_role, scope_student
from app.api.errors import ApiError
from app.domain.calendar import AS_OF

router = APIRouter(tags=["students"])


@router.get("/students", dependencies=[require_role(*STAFF)])
def list_students(conn: Conn, user: CurrentUser, page: Annotated[Page, Depends()],
                  q: Annotated[str | None, Query(max_length=40, pattern=r"^[^\x00-\x1f]*$")] = None,
                  program_id: Annotated[str | None, Query(pattern=r"^PRG-\d{2}$")] = None,
                  owing: bool | None = None, flagged: bool | None = None):
    money = user.role != "INSTRUCTOR"
    scoped = program_id if money else user.program_id
    rows = conn.execute(text("""
        SELECT s.student_id, s.full_name, s.email, s.program_id, s.residency,
               b.balance_paise, b.charged_paise, b.paid_paise,
               (SELECT count(*) FROM exception x
                 WHERE x.student_id = s.student_id AND x.status = 'OPEN') AS open_exceptions
        FROM student s JOIN student_balance b USING (student_id)
        WHERE (CAST(:after AS text) IS NULL OR s.student_id > :after)
          AND (CAST(:program AS text) IS NULL OR s.program_id = :program)
          AND (CAST(:q AS text) IS NULL OR s.student_id ILIKE :like OR s.full_name ILIKE :like
               OR s.email ILIKE :like)
          AND (CAST(:owing AS boolean) IS NULL OR (b.balance_paise > 0) = :owing)
          AND (CAST(:flagged AS boolean) IS NULL OR EXISTS (SELECT 1 FROM exception x
               WHERE x.student_id = s.student_id AND x.status = 'OPEN') = :flagged)
        ORDER BY s.student_id LIMIT :n"""),
        {"after": page.after, "program": scoped, "q": q, "like": f"%{q}%" if q else None,
         "owing": owing if money else None, "flagged": flagged if money else None,
         "n": page.limit + 1}).mappings().all()
    items = [dict(r) for r in rows]
    if not money:
        for r in items:
            for k in ("balance_paise", "charged_paise", "paid_paise", "open_exceptions"):
                r.pop(k)
    return page.wrap(items, "student_id")


@router.get("/students/{student_id}")
def student(student_id: str, conn: Conn, user: CurrentUser):
    scope_student(conn, user, student_id)
    profile = conn.execute(text("SELECT s.*, p.name AS program_name FROM student s JOIN program p USING (program_id)"
                                " WHERE student_id = :s"), {"s": student_id}).mappings().one()
    enrollments = conn.execute(text("""SELECT e.enrollment_id, e.term_id, t.term_name, e.status, e.enrolled_on,
                                              e.left_on
                                       FROM enrollment e JOIN term t USING (term_id) WHERE e.student_id = :s
                                       ORDER BY t.start_date"""), {"s": student_id}).mappings().all()
    out = {"student": dict(profile), "enrollments": [dict(r) for r in enrollments], "as_of": AS_OF}
    if user.role == "INSTRUCTOR":
        return out
    out["invoices"] = [dict(r) for r in conn.execute(text(
        "SELECT invoice_id, term_id, issue_date, due_date, status, total_paise FROM invoice WHERE student_id = :s"
        " ORDER BY issue_date, invoice_id"), {"s": student_id}).mappings().all()]
    out["balance"] = _balance(conn, student_id)
    return out


def _balance(conn, student_id: str) -> dict:
    """The stated balance next to two independent routes to the same number (R-LED-3)."""
    r = conn.execute(text("""
        SELECT b.balance_paise AS stated, b.charged_paise, b.credits_paise, b.paid_paise, b.refunded_paise, b.as_of,
          (SELECT coalesce(sum(amount_paise), 0) FROM ledger_entry WHERE student_id = :s) AS ledger,
          (SELECT coalesce(sum(total_paise), 0) FROM invoice WHERE student_id = :s)
            - (SELECT coalesce(sum(amount_paise), 0) FROM payment WHERE student_id = :s)
            + (SELECT coalesce(sum(amount_paise), 0) FROM refund WHERE student_id = :s) AS from_documents
        FROM student_balance b WHERE b.student_id = :s"""), {"s": student_id}).mappings().one()
    d = dict(r)
    d["reconciled"] = d["stated"] == d["ledger"] == d["from_documents"]
    return d


@router.get("/students/{student_id}/ledger", dependencies=[require_role("LEARNER", *FINANCE)])
def ledger(student_id: str, conn: Conn, user: CurrentUser):
    scope_student(conn, user, student_id)
    rows = conn.execute(text("""
        SELECT entry_id, posted_on, entry_type, amount_paise, source_type, source_id,
               sum(amount_paise) OVER (ORDER BY posted_on, entry_id) AS running_balance_paise
        FROM ledger_entry WHERE student_id = :s ORDER BY posted_on, entry_id LIMIT 1000"""),
        {"s": student_id}).mappings().all()
    return {"items": [dict(r) for r in rows], "balance": _balance(conn, student_id)}


@router.get("/students/{student_id}/events", dependencies=[require_role("LEARNER", *FINANCE)])
def events(student_id: str, conn: Conn, user: CurrentUser):
    scope_student(conn, user, student_id)
    rows = conn.execute(text("""
        SELECT event_id, entity_type, entity_id, from_status, to_status, occurred_on, actor FROM event
        WHERE entity_id IN (
              SELECT invoice_id FROM invoice WHERE student_id = :s
              UNION ALL SELECT enrollment_id FROM enrollment WHERE student_id = :s
              UNION ALL SELECT payment_id FROM payment WHERE student_id = :s
              UNION ALL SELECT refund_id FROM refund WHERE student_id = :s
              UNION ALL SELECT scholarship_id FROM scholarship WHERE student_id = :s
              UNION ALL SELECT eligibility_id FROM eligibility WHERE student_id = :s)
        ORDER BY occurred_on, event_id LIMIT 1000"""), {"s": student_id}).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.get("/invoices/{invoice_id}", dependencies=[require_role("LEARNER", *FINANCE)])
def invoice(invoice_id: str, conn: Conn, user: CurrentUser):
    check_id("invoice", invoice_id)
    inv = conn.execute(text("SELECT * FROM invoice WHERE invoice_id = :i"), {"i": invoice_id}).mappings().first()
    if inv is None:
        raise ApiError(404, "NOT_FOUND", "No such invoice.")
    scope_student(conn, user, inv["student_id"])
    lines = conn.execute(text("""
        SELECT l.invoice_line_id, l.line_no, l.line_type, l.description, l.amount_paise, l.posted_on,
               l.applies_to_line_id, coalesce(sum(a.amount_paise), 0) AS allocated_paise
        FROM invoice_line l LEFT JOIN payment_allocation a USING (invoice_line_id)
        WHERE l.invoice_id = :i GROUP BY l.invoice_line_id ORDER BY l.line_no"""),
        {"i": invoice_id}).mappings().all()
    items = [dict(r) for r in lines]
    credit: dict[str, int] = {}
    for ln in items:
        if ln["applies_to_line_id"]:
            credit[ln["applies_to_line_id"]] = credit.get(ln["applies_to_line_id"], 0) + ln["amount_paise"]
    for ln in items:
        charge = ln["line_type"] in ("FEE", "LATE_FEE")
        ln["outstanding_paise"] = (ln["amount_paise"] + credit.get(ln["invoice_line_id"], 0)
                                   - ln["allocated_paise"]) if charge else None
    history = conn.execute(text("SELECT event_id, from_status, to_status, occurred_on, actor FROM event"
                                " WHERE entity_type = 'invoice' AND entity_id = :i ORDER BY occurred_on, event_id"),
                           {"i": invoice_id}).mappings().all()
    return {"invoice": dict(inv), "lines": items, "history": [dict(h) for h in history]}
