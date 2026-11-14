"""Self-service for learners: sign up, see what they can enrol in, enrol (which bills them and decides scholarships),
see their own awards and fees. The enrolment itself is a function so staff can enrol a student through the same code."""
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Connection, text

from app import ids, security
from app.api import txn
from app.api.deps import Conn, CurrentUser, require_role
from app.api.errors import ApiError
from app.domain import billing, ledger, scholarships
from app.domain.calendar import AS_OF, term_of

router = APIRouter(prefix="/me", tags=["learner"], dependencies=[require_role("LEARNER")])
Scheme = Literal["MERIT_GOLD", "MERIT_SILVER", "NEED_BASED", "SPORTS", "INTL_EXCELLENCE"]


class Signup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(pattern=r"^[^@\s]{1,60}@[^@\s]{1,40}\.[^@\s]{2,20}$", max_length=80)
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=2, max_length=80)
    program_id: str = Field(pattern=r"^PRG-\d{2}$")
    residency: Literal["DOMESTIC", "INTERNATIONAL"]
    gpa: float = Field(ge=0, le=10)
    income_band: Literal["LOW", "MID", "HIGH", "AFFLUENT"]
    sports_quota: bool = False
    hostel_resident: bool = False


class Enroll(BaseModel):
    model_config = ConfigDict(extra="forbid")
    term_id: str = Field(pattern=r"^TERM-\d{4}-(SPRING|SUMMER|FALL)$")
    applications: list[Scheme] = Field(default_factory=list, max_length=5)


def new_student(conn: Connection, counters, f: dict) -> str:
    """Insert one student and an empty balance row; returns the new id. The student record carries a reserved
    @example.edu address (the data rule); a login, if any, keeps the address the person typed."""
    sid = ids.student_id(counters.take("student"))
    txn.insert_row(conn, "student", {
        "student_id": sid, "program_id": f["program_id"], "full_name": f["full_name"].strip(), "email": f"{sid.lower()}@example.edu",
        "residency": f["residency"], "gpa": round(f["gpa"], 2), "income_band": f["income_band"], "sports_quota": f["sports_quota"],
        "hostel_resident": f["hostel_resident"], "waiver_type": f.get("waiver_type"), "admitted_on": AS_OF})
    conn.execute(text("INSERT INTO student_balance (student_id, charged_paise, credits_paise, paid_paise, refunded_paise,"
                      " balance_paise, as_of) VALUES (:s, 0, 0, 0, 0, 0, :d)"), {"s": sid, "d": AS_OF})
    return sid


def create_account(conn: Connection, body: Signup) -> dict:
    """A new synthetic student plus a learner login, in one transaction. The student's own record carries a
    reserved @example.edu address (the data rule); the login keeps the address the person typed."""
    if conn.execute(text("SELECT 1 FROM program WHERE program_id = :p"), {"p": body.program_id}).first() is None:
        raise ApiError(422, "VALIDATION", "program_id: no such program")
    counters = txn.begin_write(conn)
    if conn.execute(text("SELECT 1 FROM app_user WHERE lower(email) = :e"), {"e": body.email.lower()}).first():
        raise ApiError(409, "EMAIL_TAKEN", "That email already has an account. Sign in instead.")
    sid = new_student(conn, counters, {**body.model_dump(exclude={"email", "password"}), "waiver_type": None})
    user = {"app_user_id": ids.user_id(counters.take("user")), "email": body.email.strip(), "role": "LEARNER",
            "student_id": sid, "program_id": None, "enabled": True, "created_at": datetime.now(UTC),
            "password_hash": security.hash_password(body.password)}
    txn.insert_row(conn, "app_user", user)
    conn.commit()
    return user


def _student(conn: Connection, student_id: str) -> dict:
    row = conn.execute(text("SELECT * FROM student WHERE student_id = :s"), {"s": student_id}).mappings().first()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "No such student.")
    return dict(row)


def _open_terms(conn: Connection, student_id: str) -> list[dict]:
    """Terms still running or ahead (not ended by the as-of date) in which the student has no enrolment yet."""
    rows = conn.execute(text("""
        SELECT t.* FROM term t
        WHERE t.end_date > :d AND NOT EXISTS (SELECT 1 FROM enrollment e WHERE e.student_id = :s AND e.term_id = t.term_id)
        ORDER BY t.start_date"""), {"d": AS_OF, "s": student_id}).mappings().all()
    return [dict(r) for r in rows]


def _fee_rows(conn: Connection, program_id: str, term_id: str) -> list[dict]:
    return [dict(r) for r in conn.execute(text("SELECT * FROM fee_schedule WHERE program_id = :p AND term_id = :t"),
                                          {"p": program_id, "t": term_id}).mappings()]


def preview(conn: Connection, student_id: str) -> list[dict]:
    """For each open term: the lines the student would be billed, and which schemes they meet today."""
    student = _student(conn, student_id)
    out = []
    for term in _open_terms(conn, student_id):
        t = term_of(term["term_id"])
        fee_rows = _fee_rows(conn, student["program_id"], term["term_id"])
        lines = billing.build_invoice_lines("PREVIEW", student, fee_rows, t.issue)
        fee_by_id = {r["fee_schedule_id"]: r for r in fee_rows}
        eligible = billing.eligible_fees(lines, fee_by_id)
        schemes = []
        for s in scholarships.SCHEMES:
            decision, reason = scholarships.judge(student, s, True)
            schemes.append({"scheme_code": s.code, "name": s.name, "meets_criteria": decision == "ELIGIBLE", "reason": reason,
                            "would_award_paise": min(scholarships.computed_amount(s, eligible), eligible)
                            if decision == "ELIGIBLE" else 0})
        out.append({"term": term, "lines": [{"description": ln["description"], "amount_paise": ln["amount_paise"]}
                                            for ln in lines],
                    "total_paise": billing.invoice_total(lines), "eligible_fees_paise": eligible, "schemes": schemes})
    return out


def enroll_student(conn: Connection, student_id: str, term_id: str, applications: list[str], actor: str) -> dict:
    """Enrol, bill (R-BILL), decide scholarships (R-SCH), and write the ledger and events: one transaction.

    Dates follow the term calendar (enrolled on the first day, invoice issued on the term's issue date) so the new rows
    obey the same rules as the generated ones; the payment and withdrawal endpoints date their own actions at AS_OF."""
    txn.lock_student(conn, student_id)
    counters = txn.begin_write(conn)
    student = _student(conn, student_id)
    open_terms = {t["term_id"]: t for t in _open_terms(conn, student_id)}
    if term_id not in open_terms:
        raise ApiError(409, "CANNOT_ENROLL", "You are already enrolled in that term, or it has ended.")
    term = term_of(term_id)
    sno = ids.student_no(student_id)
    fee_rows = _fee_rows(conn, student["program_id"], term_id)
    if not fee_rows:
        raise ApiError(409, "NO_FEES", "No fees are published for your program in that term yet.")
    seq = conn.execute(text("SELECT count(*) FROM invoice WHERE student_id = :s"), {"s": student_id}).scalar() + 1
    invoice_id = ids.invoice_id(sno, seq)
    try:
        lines = billing.build_invoice_lines(invoice_id, student, fee_rows, term.issue)
    except ValueError as exc:                                    # overlapping fee versions: refuse rather than double bill
        raise ApiError(409, "FEE_SCHEDULE_CONFLICT", str(exc)) from exc
    fee_by_id = {r["fee_schedule_id"]: r for r in fee_rows}
    enrollment = {"enrollment_id": ids.enrollment_id(sno, term.name), "student_id": student_id,
                  "program_id": student["program_id"], "term_id": term_id, "enrolled_on": term.start,
                  "status": "ENROLLED", "left_on": None}
    txn.insert_row(conn, "enrollment", enrollment)
    txn.add_event(conn, counters, "enrollment", enrollment["enrollment_id"], None, "ENROLLED", term.start, actor)

    awarded = None
    if applications:
        outcome = scholarships.decide(student, billing.eligible_fees(lines, fee_by_id), applications)
        winner_elg = None
        for code, decision, reason in outcome.decisions:
            eid = ids.eligibility_id(counters.take("eligibility"))
            txn.insert_row(conn, "eligibility", {
                "eligibility_id": eid, "student_id": student_id, "term_id": term_id, "scheme_code": code,
                "decision": decision, "reason_code": reason, "gpa_at_decision": student["gpa"],
                "income_band_at_decision": student["income_band"], "decided_on": term.issue})
            txn.add_event(conn, counters, "eligibility", eid, None, decision, term.issue, actor)
            if decision == "ELIGIBLE":
                winner_elg = eid
        if outcome.award:
            sid = ids.scholarship_id(counters.take("scholarship"))
            lines += scholarships.credit_lines(invoice_id, sid, outcome.award.amount_paise, lines, fee_by_id, term.issue,
                                               len(lines) + 1)
            awarded = {"scholarship_id": sid, "eligibility_id": winner_elg, "student_id": student_id, "term_id": term_id,
                       "scheme_code": outcome.award.scheme_code, "invoice_id": invoice_id,
                       "eligible_fees_paise": outcome.award.eligible_fees_paise,
                       "amount_paise": outcome.award.amount_paise, "status": "APPLIED", "awarded_on": term.issue}

    invoice = {"invoice_id": invoice_id, "student_id": student_id, "enrollment_id": enrollment["enrollment_id"],
               "term_id": term_id, "issue_date": term.issue, "due_date": term.due, "status": "ISSUED",
               "total_paise": billing.invoice_total(lines)}
    txn.insert_row(conn, "invoice", invoice)                     # parent first: lines and the award point at it
    if awarded:
        txn.insert_row(conn, "scholarship", awarded)
    for line in lines:
        txn.insert_row(conn, "invoice_line", line)
        txn.add_ledger(conn, counters, ledger.entry_for_line(student_id, line))
    txn.add_event(conn, counters, "invoice", invoice_id, None, "ISSUED", term.issue, actor)
    if awarded:
        txn.add_event(conn, counters, "scholarship", awarded["scholarship_id"], None, "AWARDED", term.issue, actor)
        txn.add_event(conn, counters, "scholarship", awarded["scholarship_id"], "AWARDED", "APPLIED", term.issue, actor)
    balance = txn.refresh_balance(conn, student_id, AS_OF)
    conn.commit()
    return {"enrollment": enrollment, "invoice": invoice, "lines": lines, "scholarship": awarded, "balance": balance}


@router.get("/enrollable")
def enrollable(conn: Conn, user: CurrentUser):
    return {"items": preview(conn, user.student_id)}


@router.post("/enroll", status_code=201)
def enroll(body: Enroll, conn: Conn, user: CurrentUser):
    return enroll_student(conn, user.student_id, body.term_id, list(dict.fromkeys(body.applications)), user.app_user_id)


@router.get("/scholarships")
def my_scholarships(conn: Conn, user: CurrentUser):
    awards = conn.execute(text("""SELECT s.*, c.name AS scheme_name FROM scholarship s
                                  JOIN scholarship_scheme c USING (scheme_code) WHERE s.student_id = :s ORDER BY s.awarded_on"""),
                          {"s": user.student_id}).mappings().all()
    decisions = conn.execute(text("""SELECT e.*, c.name AS scheme_name FROM eligibility e
                                     JOIN scholarship_scheme c USING (scheme_code) WHERE e.student_id = :s
                                     ORDER BY e.decided_on, e.eligibility_id"""), {"s": user.student_id}).mappings().all()
    return {"awards": [dict(a) for a in awards], "decisions": [dict(d) for d in decisions]}


@router.get("/fees")
def my_fees(conn: Conn, user: CurrentUser, term_id: Annotated[str | None, Query(max_length=40)] = None):
    student = _student(conn, user.student_id)
    rows = conn.execute(text("""SELECT f.*, t.term_name FROM fee_schedule f JOIN term t USING (term_id)
                                WHERE f.program_id = :p AND (CAST(:t AS text) IS NULL OR f.term_id = :t)
                                ORDER BY t.start_date, f.fee_type, f.version"""),
                        {"p": student["program_id"], "t": term_id}).mappings().all()
    return {"program_id": student["program_id"], "items": [dict(r) for r in rows]}
