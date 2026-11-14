"""Staff data entry and administration: fee schedule versions, adding students, editing profiles, assigning a
scholarship to an existing invoice, and user accounts. Every route is role-guarded (docs/permissions.md is generated
from those guards)."""
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app import ids, security
from app.api import learner, txn
from app.api.deps import Conn, CurrentUser, check_id, require_role
from app.api.errors import ApiError
from app.domain import billing, scholarships, status
from app.domain.billing import outstanding_by_line
from app.domain.calendar import AS_OF

router = APIRouter(tags=["admin"])
ADMINS = ("ACADEMIC_ADMIN", "PLATFORM_ADMIN")
STAFF_DATA = ("ACADEMIC_ADMIN", "SUPPORT", "PLATFORM_ADMIN")
FeeType = Literal["TUITION", "LAB", "LIBRARY", "TECHNOLOGY", "EXAM", "INTL_SURCHARGE", "HOSTEL"]


# ------------------------------------------------------------------------------------------ fee schedules
class NewFee(BaseModel):
    model_config = ConfigDict(extra="forbid")
    program_id: str = Field(pattern=r"^PRG-\d{2}$")
    term_id: str = Field(pattern=r"^TERM-\d{4}-(SPRING|SUMMER|FALL)$")
    fee_type: FeeType
    applies_to: Literal["ALL", "INTERNATIONAL", "HOSTEL"]
    amount_paise: int = Field(ge=100, le=1_000_000_000)
    effective_from: date
    scholarship_eligible: bool = True


@router.post("/fee-schedules", status_code=201, dependencies=[require_role(*ADMINS)])
def new_fee_version(body: NewFee, conn: Conn):
    """Publish a new price version. The previous version of the same fee is closed the day before this one starts, so
    exactly one version is in force on any date (R-FEE-2). Invoices already issued keep the version they were billed on."""
    txn.begin_write(conn)
    term = conn.execute(text("SELECT term_id, term_name, year FROM term WHERE term_id = :t"), {"t": body.term_id}).mappings().first()
    if term is None or conn.execute(text("SELECT 1 FROM program WHERE program_id = :p"), {"p": body.program_id}).first() is None:
        raise ApiError(404, "NOT_FOUND", "No such program or term.")
    rows = conn.execute(text("SELECT * FROM fee_schedule WHERE program_id = :p AND term_id = :t AND fee_type = :f ORDER BY version"),
                        {"p": body.program_id, "t": body.term_id, "f": body.fee_type}).mappings().all()
    if any(r["applies_to"] != body.applies_to for r in rows):
        raise ApiError(409, "AUDIENCE_CONFLICT", "That fee already exists for a different audience; versions must keep one audience.")
    prev = rows[-1] if rows else None
    if prev and body.effective_from <= prev["effective_from"]:
        raise ApiError(409, "DATE_ORDER", f"The new version must start after the current one ({prev['effective_from']}).")
    if prev and (prev["effective_to"] is None or prev["effective_to"] >= body.effective_from):
        conn.execute(text("UPDATE fee_schedule SET effective_to = :d WHERE fee_schedule_id = :i"),
                     {"d": body.effective_from - timedelta(days=1), "i": prev["fee_schedule_id"]})
    version = (prev["version"] + 1) if prev else 1
    row = {"fee_schedule_id": ids.fee_schedule_id(body.program_id, term["term_name"], body.fee_type, version, term["year"]),
           "program_id": body.program_id, "term_id": body.term_id, "fee_type": body.fee_type, "applies_to": body.applies_to,
           "amount_paise": body.amount_paise, "version": version, "effective_from": body.effective_from, "effective_to": None,
           "scholarship_eligible": body.scholarship_eligible}
    txn.insert_row(conn, "fee_schedule", row)
    conn.commit()
    return row


# ------------------------------------------------------------------------------------------ students
class NewStudent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str = Field(min_length=2, max_length=80)
    program_id: str = Field(pattern=r"^PRG-\d{2}$")
    residency: Literal["DOMESTIC", "INTERNATIONAL"]
    gpa: float = Field(ge=0, le=10)
    income_band: Literal["LOW", "MID", "HIGH", "AFFLUENT"]
    sports_quota: bool = False
    hostel_resident: bool = False
    waiver_type: Literal["STAFF_WARD", "SIBLING", "HARDSHIP"] | None = None
    login_email: str | None = Field(default=None, pattern=r"^[^@\s]{1,60}@[^@\s]{1,40}\.[^@\s]{2,20}$", max_length=80)
    login_password: str | None = Field(default=None, min_length=12, max_length=128)


@router.post("/students", status_code=201, dependencies=[require_role(*STAFF_DATA)])
def add_student(body: NewStudent, conn: Conn):
    """Add a student (and, if an email and password are given, a learner login for them)."""
    if bool(body.login_email) != bool(body.login_password):
        raise ApiError(422, "VALIDATION", "login_email and login_password must be given together")
    if conn.execute(text("SELECT 1 FROM program WHERE program_id = :p"), {"p": body.program_id}).first() is None:
        raise ApiError(422, "VALIDATION", "program_id: no such program")
    counters = txn.begin_write(conn)
    if body.login_email and conn.execute(text("SELECT 1 FROM app_user WHERE lower(email) = :e"), {"e": body.login_email.lower()}).first():
        raise ApiError(409, "EMAIL_TAKEN", "That email already has an account.")
    sid = learner.new_student(conn, counters, body.model_dump(exclude={"login_email", "login_password"}))
    login = None
    if body.login_email:
        login = {"app_user_id": ids.user_id(counters.take("user")), "email": body.login_email.strip(), "role": "LEARNER",
                 "student_id": sid, "program_id": None, "enabled": True, "created_at": datetime.now(UTC),
                 "password_hash": security.hash_password(body.login_password)}
        txn.insert_row(conn, "app_user", login)
    conn.commit()
    return {"student_id": sid, "login": {"app_user_id": login["app_user_id"], "email": login["email"]} if login else None}


class StaffProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = Field(default=None, min_length=2, max_length=80)
    residency: Literal["DOMESTIC", "INTERNATIONAL"] | None = None
    gpa: float | None = Field(default=None, ge=0, le=10)
    income_band: Literal["LOW", "MID", "HIGH", "AFFLUENT"] | None = None
    sports_quota: bool | None = None
    hostel_resident: bool | None = None
    waiver_type: Literal["STAFF_WARD", "SIBLING", "HARDSHIP", "NONE"] | None = None


class OwnProfile(BaseModel):
    """A learner may correct their name and housing; academic and income facts are changed by staff."""
    model_config = ConfigDict(extra="forbid")
    full_name: str | None = Field(default=None, min_length=2, max_length=80)
    hostel_resident: bool | None = None


def _update_profile(conn, student_id: str, fields: dict) -> dict:
    fields = {k: v for k, v in fields.items() if v is not None}
    if not fields:
        raise ApiError(422, "VALIDATION", "Nothing to change.")
    if "waiver_type" in fields and fields["waiver_type"] == "NONE":
        fields["waiver_type"] = None
    sets = {c: fields[c] for c in ("full_name", "residency", "gpa", "income_band", "sports_quota", "hostel_resident", "waiver_type")
            if c in fields or (c == "waiver_type" and "waiver_type" in fields)}
    txn.lock_student(conn, student_id)
    from app import schema
    table = schema.TABLES["student"]
    conn.execute(table.update().where(table.c.student_id == student_id).values(**sets))     # bound, columns from a fixed list
    conn.commit()
    return {"student_id": student_id, "changed": sorted(sets)}


@router.post("/students/{student_id}/profile", dependencies=[require_role(*STAFF_DATA)])
def edit_profile(student_id: str, body: StaffProfile, conn: Conn):
    check_id("student", student_id)
    if conn.execute(text("SELECT 1 FROM student WHERE student_id = :s"), {"s": student_id}).first() is None:
        raise ApiError(404, "NOT_FOUND", "No such student.")
    return _update_profile(conn, student_id, body.model_dump())


@router.post("/me/profile", dependencies=[require_role("LEARNER")])
def edit_own_profile(body: OwnProfile, conn: Conn, user: CurrentUser):
    return _update_profile(conn, user.student_id, body.model_dump())


# ------------------------------------------------------------------------------------------ scholarships
class AssignAward(BaseModel):
    model_config = ConfigDict(extra="forbid")
    term_id: str = Field(pattern=r"^TERM-\d{4}-(SPRING|SUMMER|FALL)$")
    scheme_code: Literal["MERIT_GOLD", "MERIT_SILVER", "NEED_BASED", "SPORTS", "INTL_EXCELLENCE"]


@router.post("/students/{student_id}/scholarships", status_code=201, dependencies=[require_role(*ADMINS)])
def assign_scholarship(student_id: str, body: AssignAward, conn: Conn, user: CurrentUser):
    """Apply one scheme to a student's live invoice that has no award yet (a late application). The student must still
    meet the scheme's criteria: staff apply the rules, they cannot waive them. Refused if payments already cover more than
    the reduced invoice would leave (that case needs a withdrawal and refund, not an award)."""
    check_id("student", student_id)
    if conn.execute(text("SELECT 1 FROM student WHERE student_id = :s"), {"s": student_id}).first() is None:
        raise ApiError(404, "NOT_FOUND", "No such student.")
    txn.lock_student(conn, student_id)
    counters = txn.begin_write(conn)
    student = learner._student(conn, student_id)
    enr = conn.execute(text("SELECT * FROM enrollment WHERE student_id = :s AND term_id = :t"),
                       {"s": student_id, "t": body.term_id}).mappings().first()
    if enr is None or enr["status"] != "ENROLLED":
        raise ApiError(409, "NOT_ENROLLED", "The student is not currently enrolled in that term.")
    inv = conn.execute(text("SELECT * FROM invoice WHERE enrollment_id = :e AND status NOT IN ('VOID', 'CANCELLED') ORDER BY invoice_id LIMIT 1"),
                       {"e": enr["enrollment_id"]}).mappings().first()
    if inv is None:
        raise ApiError(409, "NO_INVOICE", "There is no live invoice to apply an award to.")
    if conn.execute(text("SELECT 1 FROM scholarship WHERE invoice_id = :i AND status <> 'REVOKED'"), {"i": inv["invoice_id"]}).first():
        raise ApiError(409, "ALREADY_AWARDED", "That invoice already has a scholarship.")
    lines = [dict(r) for r in conn.execute(text("SELECT * FROM invoice_line WHERE invoice_id = :i ORDER BY line_no"), {"i": inv["invoice_id"]}).mappings()]
    allocs = [dict(r) for r in conn.execute(text(
        "SELECT a.* FROM payment_allocation a JOIN invoice_line l USING (invoice_line_id) WHERE l.invoice_id = :i"), {"i": inv["invoice_id"]}).mappings()]
    fee_by_id = {r["fee_schedule_id"]: r for r in learner._fee_rows(conn, student["program_id"], body.term_id)}
    eligible = billing.eligible_fees(lines, fee_by_id)
    outcome = scholarships.decide(student, eligible, [body.scheme_code])
    code, decision, reason = outcome.decisions[0]
    eid = ids.eligibility_id(counters.take("eligibility"))
    txn.insert_row(conn, "eligibility", {"eligibility_id": eid, "student_id": student_id, "term_id": body.term_id, "scheme_code": code,
                                         "decision": decision, "reason_code": reason, "gpa_at_decision": student["gpa"],
                                         "income_band_at_decision": student["income_band"], "decided_on": AS_OF})
    txn.add_event(conn, counters, "eligibility", eid, None, decision, AS_OF, user.app_user_id)
    if outcome.award is None:
        conn.commit()                                          # the refusal itself is recorded: who was judged, and why not
        raise ApiError(422, "NOT_ELIGIBLE", f"The student does not qualify: {reason.replace('_', ' ').lower()}.")
    sid = ids.scholarship_id(counters.take("scholarship"))
    new_lines = scholarships.credit_lines(inv["invoice_id"], sid, outcome.award.amount_paise, lines, fee_by_id, AS_OF, len(lines) + 1)
    if any(v < 0 for v in outstanding_by_line(lines + new_lines, allocs).values()):
        conn.rollback()
        raise ApiError(409, "ALREADY_PAID", "Payments already cover more than the invoice would be after this award; use a withdrawal and refund.")
    award = {"scholarship_id": sid, "eligibility_id": eid, "student_id": student_id, "term_id": body.term_id, "scheme_code": code,
             "invoice_id": inv["invoice_id"], "eligible_fees_paise": outcome.award.eligible_fees_paise,
             "amount_paise": outcome.award.amount_paise, "status": "APPLIED", "awarded_on": AS_OF}
    txn.insert_row(conn, "scholarship", award)
    from app.domain import ledger
    for line in new_lines:
        txn.insert_row(conn, "invoice_line", line)
        txn.add_ledger(conn, counters, ledger.entry_for_line(student_id, line))
    txn.add_event(conn, counters, "scholarship", sid, None, "AWARDED", AS_OF, user.app_user_id)
    txn.add_event(conn, counters, "scholarship", sid, "AWARDED", "APPLIED", AS_OF, user.app_user_id)
    all_lines = lines + new_lines
    total = billing.invoice_total(all_lines)
    new_status = status.invoice_status(False, False, sum(outstanding_by_line(all_lines, allocs).values()),
                                       sum(a["amount_paise"] for a in allocs), inv["due_date"], AS_OF)
    conn.execute(text("UPDATE invoice SET total_paise = :t, status = :s WHERE invoice_id = :i"), {"t": total, "s": new_status, "i": inv["invoice_id"]})
    if new_status != inv["status"] and status.is_allowed("invoice", inv["status"], new_status):
        txn.add_event(conn, counters, "invoice", inv["invoice_id"], inv["status"], new_status, AS_OF, user.app_user_id)
    balance = txn.refresh_balance(conn, student_id, AS_OF)
    conn.commit()
    return {"scholarship": award, "lines": new_lines, "invoice": {"invoice_id": inv["invoice_id"], "total_paise": total, "status": new_status},
            "balance": balance}


# ------------------------------------------------------------------------------------------ user accounts
class NewUser(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(pattern=r"^[^@\s]{1,60}@[^@\s]{1,40}\.[^@\s]{2,20}$", max_length=80)
    password: str = Field(min_length=12, max_length=128)
    role: Literal["LEARNER", "INSTRUCTOR", "ACADEMIC_ADMIN", "SUPPORT", "PLATFORM_ADMIN"]
    student_id: str | None = Field(default=None, pattern=r"^STU-\d{6}$")
    program_id: str | None = Field(default=None, pattern=r"^PRG-\d{2}$")


class Enabled(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


@router.get("/admin/users", dependencies=[require_role("PLATFORM_ADMIN")])
def list_users(conn: Conn):
    rows = conn.execute(text("SELECT app_user_id, email, role, student_id, program_id, enabled, created_at FROM app_user ORDER BY app_user_id")).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.post("/admin/users", status_code=201, dependencies=[require_role("PLATFORM_ADMIN")])
def create_user(body: NewUser, conn: Conn):
    """Create a login for any role. A learner login must name an existing student; an instructor login names a program."""
    if (body.role == "LEARNER") != (body.student_id is not None):
        raise ApiError(422, "VALIDATION", "student_id is required for a LEARNER login and not allowed for other roles")
    if (body.role == "INSTRUCTOR") != (body.program_id is not None):
        raise ApiError(422, "VALIDATION", "program_id is required for an INSTRUCTOR login and not allowed for other roles")
    if body.student_id and conn.execute(text("SELECT 1 FROM student WHERE student_id = :s"), {"s": body.student_id}).first() is None:
        raise ApiError(404, "NOT_FOUND", "No such student.")
    if body.program_id and conn.execute(text("SELECT 1 FROM program WHERE program_id = :p"), {"p": body.program_id}).first() is None:
        raise ApiError(404, "NOT_FOUND", "No such program.")
    counters = txn.begin_write(conn)
    if conn.execute(text("SELECT 1 FROM app_user WHERE lower(email) = :e"), {"e": body.email.lower()}).first():
        raise ApiError(409, "EMAIL_TAKEN", "That email already has an account.")
    user = {"app_user_id": ids.user_id(counters.take("user")), "email": body.email.strip(), "role": body.role, "student_id": body.student_id,
            "program_id": body.program_id, "enabled": True, "created_at": datetime.now(UTC), "password_hash": security.hash_password(body.password)}
    txn.insert_row(conn, "app_user", user)
    conn.commit()
    return {k: user[k] for k in ("app_user_id", "email", "role", "student_id", "program_id", "enabled")}


@router.post("/admin/users/{app_user_id}/enabled", dependencies=[require_role("PLATFORM_ADMIN")])
def set_enabled(app_user_id: str, body: Enabled, conn: Conn, user: CurrentUser):
    if app_user_id == user.app_user_id and not body.enabled:
        raise ApiError(409, "SELF_DISABLE", "You cannot disable your own login.")
    done = conn.execute(text("UPDATE app_user SET enabled = :e WHERE app_user_id = :u"), {"e": body.enabled, "u": app_user_id}).rowcount
    if not done:
        raise ApiError(404, "NOT_FOUND", "No such user.")
    conn.commit()
    return {"app_user_id": app_user_id, "enabled": body.enabled}
