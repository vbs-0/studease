"""Single source of truth for every table.

`Column.info` carries the data dictionary (description, allowed values, unit, validation rule). The Alembic
migration, the SQL seed DDL, CSV column order, enum validation and docs/data_dictionary.md are all derived
from this module, so they cannot drift apart.

Money is always integer paise (`*_paise`). Dates are calendar dates; the simulation is day-granular.
"""
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.enums import (  # noqa: F401  (re-exported for callers that import them from schema)
    APPLIES_TO,
    AWARD_TYPES,
    CHARGE_TYPES,
    CREDIT_TYPES,
    DECISIONS,
    DECISIONS_EXPECTED,
    ENROLLMENT_STATUSES,
    ENTITY_TYPES,
    EXCEPTION_STATUSES,
    FEE_TYPES,
    INCOME_BANDS,
    INVOICE_STATUSES,
    ISSUE_TYPES,
    LEDGER_TYPES,
    LEVELS,
    LINE_TYPES,
    PAYMENT_METHODS,
    PAYMENT_STATUSES,
    REASON_CODES,
    REFUND_REASONS,
    REFUND_STATUSES,
    RESIDENCY,
    ROLES,
    SCHOLARSHIP_STATUSES,
    TERM_NAMES,
    WAIVER_TYPES,
)

metadata = MetaData(naming_convention={
    "ix": "ix_%(table_name)s_%(column_0_N_name)s", "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s", "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s"})

ID, LONG_ID = String(32), String(64)


def col(name, type_, desc, *extra, fk=None, pk=False, null=False, allowed=None, unit=None, unique=False,
        rule=None, **kw) -> Column:
    """A column with its data-dictionary entry. `null=True` means optional."""
    args = [ForeignKey(fk)] if isinstance(fk, str) else ([fk] if fk is not None else [])
    return Column(name, type_, *args, *extra, primary_key=pk, nullable=null and not pk, unique=unique,
                  info={"desc": desc, "allowed": allowed, "unit": unit, "rule": rule}, **kw)


def table(name, *items, schema=None, comment="") -> Table:
    """A table plus one CHECK per column that lists allowed values."""
    checks = [CheckConstraint(f"{c.name} IN ({', '.join(repr(v) for v in c.info['allowed'])})",
                              name=f"{c.name}_allowed")
              for c in items if isinstance(c, Column) and c.info.get("allowed")]
    return Table(name, metadata, *items, *checks, schema=schema, comment=comment)


# ----------------------------------------------------------------------------------------- master data
program = table(
    "program",
    col("program_id", ID, "Program id", pk=True, rule="PRG-NN"),
    col("name", String(80), "Program name", unique=True),
    col("level", String(10), "Study level", allowed=LEVELS),
    col("has_lab", Boolean, "Program charges a lab fee"),
    comment="Program: a course of study. 1:N Student, 1:N FeeSchedule, 1:N Enrollment.")

term = table(
    "term",
    col("term_id", ID, "Term id", pk=True, rule="TERM-YYYY-SPRING|SUMMER|FALL"),
    col("term_name", String(8), "Term name", allowed=TERM_NAMES),
    col("year", SmallInteger, "Calendar year"),
    col("start_date", Date, "First day of teaching"),
    col("end_date", Date, "Last day of teaching", rule=">= start_date"),
    col("invoice_issue_date", Date, "Date invoices for this term are issued", rule="< start_date"),
    col("due_date", Date, "Payment due date", rule="invoice_issue_date + 30 days"),
    CheckConstraint("end_date >= start_date", name="teaching_dates"),
    CheckConstraint("invoice_issue_date < start_date", name="issue_before_start"),
    CheckConstraint("due_date > invoice_issue_date", name="due_after_issue"),
    comment="Term: an academic term with the dates the billing rules read.")

scholarship_scheme = table(
    "scholarship_scheme",
    col("scheme_code", String(24), "Scheme code", pk=True, rule="^[A-Z_]+$"),
    col("name", String(60), "Display name"),
    col("min_gpa", Numeric(4, 2), "Minimum GPA to qualify", rule="0..10"),
    col("required_income_band", String(10), "Income band that must match, if any", null=True,
        allowed=INCOME_BANDS),
    col("requires_sports_quota", Boolean, "Student must hold a sports quota"),
    col("requires_international", Boolean, "Student must be international"),
    col("award_type", String(8), "How the award is computed", allowed=AWARD_TYPES),
    col("award_bp", Integer, "Percent of eligible fees, in basis points", null=True, unit="basis points",
        rule="1..10000 when PERCENT"),
    col("award_fixed_paise", BigInteger, "Fixed award amount", null=True, unit="paise", rule="> 0 when FIXED"),
    col("priority", SmallInteger, "Tie-break order (lower wins)", unique=True),
    CheckConstraint("min_gpa BETWEEN 0 AND 10", name="gpa_range"),
    CheckConstraint("(award_type = 'PERCENT' AND award_bp BETWEEN 1 AND 10000 AND award_fixed_paise IS NULL) "
                    "OR (award_type = 'FIXED' AND award_fixed_paise > 0 AND award_bp IS NULL)",
                    name="award_shape"),
    comment="ScholarshipScheme: the criteria and the award formula (master data).")

student = table(
    "student",
    col("student_id", ID, "Student id", pk=True, rule="STU-NNNNNN"),
    col("program_id", ID, "Program the student belongs to", fk="program.program_id"),
    col("full_name", String(80), "Synthetic name (no real person)"),
    col("email", String(80), "Synthetic email on example.edu", unique=True, rule="ends with @example.edu"),
    col("residency", String(14), "Residency status", allowed=RESIDENCY),
    col("gpa", Numeric(4, 2), "Grade point average on a 10-point scale", rule="0..10"),
    col("income_band", String(10), "Household income band", allowed=INCOME_BANDS),
    col("sports_quota", Boolean, "Holds a sports quota"),
    col("hostel_resident", Boolean, "Lives in the hostel (charged HOSTEL fee)"),
    col("waiver_type", String(12), "Fee waiver the student holds, at most one", null=True,
        allowed=WAIVER_TYPES),
    col("admitted_on", Date, "Admission date"),
    CheckConstraint("gpa BETWEEN 0 AND 10", name="gpa_range"),
    Index("ix_student_program_id", "program_id"),
    comment="Student: attributes the fee, waiver and scholarship rules read.")

fee_schedule = table(
    "fee_schedule",
    col("fee_schedule_id", LONG_ID, "Fee schedule id", pk=True, rule="FEE-PRG-NN-YYYY-TERM-TYPE-Vn"),
    col("program_id", ID, "Program", fk="program.program_id"),
    col("term_id", ID, "Term", fk="term.term_id"),
    col("fee_type", String(16), "Kind of fee", allowed=FEE_TYPES),
    col("applies_to", String(14), "Audience", allowed=APPLIES_TO),
    col("amount_paise", BigInteger, "Price of the fee", unit="paise", rule="> 0"),
    col("version", SmallInteger, "Price version for this program, term and fee type", rule=">= 1"),
    col("effective_from", Date, "First date the price applies"),
    col("effective_to", Date, "Last date the price applies; empty means open ended", null=True,
        rule=">= effective_from"),
    col("scholarship_eligible", Boolean, "Scholarships may reduce this fee"),
    CheckConstraint("amount_paise > 0", name="amount_positive"),
    CheckConstraint("version >= 1", name="version_positive"),
    CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="dates"),
    UniqueConstraint("program_id", "term_id", "fee_type", "applies_to", "effective_from",
                     name="natural_key"),
    Index("ix_fee_schedule_program_term", "program_id", "term_id"),
    comment="FeeSchedule: the effective-dated price of one fee type for a program and term.")

# ----------------------------------------------------------------------------------------- transactions
enrollment = table(
    "enrollment",
    col("enrollment_id", ID, "Enrollment id", pk=True, rule="ENR-NNNNNN-YYYY-TERM"),
    col("student_id", ID, "Student", fk="student.student_id"),
    col("program_id", ID, "Program", fk="program.program_id"),
    col("term_id", ID, "Term", fk="term.term_id"),
    col("enrolled_on", Date, "Enrollment date", rule="<= term.start_date"),
    col("status", String(10), "Current lifecycle state", allowed=ENROLLMENT_STATUSES),
    col("left_on", Date, "Date the student left", null=True, rule="set exactly when WITHDRAWN or CANCELLED"),
    CheckConstraint("(status IN ('WITHDRAWN', 'CANCELLED')) = (left_on IS NOT NULL)", name="left_on_matches"),
    UniqueConstraint("student_id", "term_id", name="student_term"),
    Index("ix_enrollment_term_id", "term_id"),
    comment="Enrollment: a student in a program for a term. Unique per student and term.")

invoice = table(
    "invoice",
    col("invoice_id", ID, "Invoice id", pk=True, rule="INV-STU-NNNNNN-YYYY-NNNNNN"),
    col("student_id", ID, "Student", fk="student.student_id"),
    col("enrollment_id", ID, "Enrollment billed", fk="enrollment.enrollment_id"),
    col("term_id", ID, "Term", fk="term.term_id"),
    col("issue_date", Date, "Issue date"),
    col("due_date", Date, "Due date", rule=">= issue_date"),
    col("status", String(14), "Derived status as of the data as-of date", allowed=INVOICE_STATUSES),
    col("total_paise", BigInteger, "Sum of all invoice lines (charges positive, credits negative)",
        unit="paise", rule="= sum(invoice_line.amount_paise)"),
    CheckConstraint("due_date >= issue_date", name="due_after_issue"),
    Index("ix_invoice_student_id", "student_id"),
    Index("ix_invoice_enrollment_id", "enrollment_id"),
    comment="Invoice: one per enrollment. A second one for the same enrollment is a labelled anomaly.")

eligibility = table(
    "eligibility",
    col("eligibility_id", ID, "Eligibility id", pk=True, rule="ELG-YYYY-NNNNNN"),
    col("student_id", ID, "Student", fk="student.student_id"),
    col("term_id", ID, "Term", fk="term.term_id"),
    col("scheme_code", String(24), "Scheme judged", fk="scholarship_scheme.scheme_code"),
    col("decision", String(10), "Decision", allowed=DECISIONS),
    col("reason_code", String(24), "Why", allowed=REASON_CODES),
    col("gpa_at_decision", Numeric(4, 2), "GPA the decision was based on"),
    col("income_band_at_decision", String(10), "Income band the decision was based on", allowed=INCOME_BANDS),
    col("decided_on", Date, "Decision date"),
    Index("ix_eligibility_student_term", "student_id", "term_id"),
    comment="Eligibility: one decision per application, with the values it was judged on and a reason.")

scholarship = table(
    "scholarship",
    col("scholarship_id", ID, "Scholarship id", pk=True, rule="SCH-YYYY-NNNNNN"),
    col("eligibility_id", ID, "The ELIGIBLE decision this award came from", fk="eligibility.eligibility_id",
        unique=True),
    col("student_id", ID, "Student", fk="student.student_id"),
    col("term_id", ID, "Term", fk="term.term_id"),
    col("scheme_code", String(24), "Scheme", fk="scholarship_scheme.scheme_code"),
    col("invoice_id", ID, "Invoice the award is applied to", fk="invoice.invoice_id"),
    col("eligible_fees_paise", BigInteger, "Scholarship-eligible fees at award time", unit="paise",
        rule=">= 0"),
    col("amount_paise", BigInteger, "Awarded amount", unit="paise", rule="0 < amount <= eligible fees"),
    col("status", String(8), "Current lifecycle state", allowed=SCHOLARSHIP_STATUSES),
    col("awarded_on", Date, "Award date"),
    CheckConstraint("amount_paise > 0", name="amount_positive"),
    Index("ix_scholarship_student_term", "student_id", "term_id"),
    comment="Scholarship: an award. 1:1 with the ELIGIBLE decision it came from.")

invoice_line = table(
    "invoice_line",
    col("invoice_line_id", LONG_ID, "Invoice line id", pk=True, rule="<invoice_id>-Lnn"),
    col("invoice_id", ID, "Invoice", fk="invoice.invoice_id"),
    col("line_no", SmallInteger, "Position within the invoice", rule=">= 1"),
    col("line_type", String(12), "Kind of line", allowed=LINE_TYPES),
    col("fee_schedule_id", LONG_ID, "Fee schedule priced (FEE lines)", null=True,
        fk="fee_schedule.fee_schedule_id"),
    col("scholarship_id", ID, "Scholarship (SCHOLARSHIP lines)", null=True, fk="scholarship.scholarship_id"),
    col("applies_to_line_id", LONG_ID, "Charge line this credit reduces", null=True,
        fk="invoice_line.invoice_line_id"),
    col("description", String(120), "Human readable description"),
    col("amount_paise", BigInteger, "Charges positive, credits negative", unit="paise"),
    col("posted_on", Date, "Date the line was posted"),
    CheckConstraint("line_no >= 1", name="line_no_positive"),
    CheckConstraint("(line_type IN ('FEE', 'LATE_FEE') AND amount_paise >= 0) OR "
                    "(line_type IN ('WAIVER', 'SCHOLARSHIP', 'ADJUSTMENT') AND amount_paise <= 0)",
                    name="sign_by_type"),
    UniqueConstraint("invoice_id", "line_no", name="invoice_line_no"),
    Index("ix_invoice_line_invoice_id", "invoice_id"),
    Index("ix_invoice_line_applies_to", "applies_to_line_id"),
    comment="InvoiceLine: a charge (positive) or a credit (negative) that points at the charge it reduces.")

payment = table(
    "payment",
    col("payment_id", ID, "Payment id", pk=True, rule="PAY-YYYY-NNNNNN"),
    col("student_id", ID, "Student", fk="student.student_id"),
    col("received_on", Date, "Date received"),
    col("amount_paise", BigInteger, "Amount received", unit="paise", rule="> 0"),
    col("method", String(14), "Payment method", allowed=PAYMENT_METHODS),
    col("reference", String(40), "External reference (synthetic)"),
    col("status", String(20), "Current allocation state", allowed=PAYMENT_STATUSES),
    CheckConstraint("amount_paise > 0", name="amount_positive"),
    Index("ix_payment_student_id", "student_id"),
    comment="Payment: money received from a student.")

payment_allocation = table(
    "payment_allocation",
    col("allocation_id", LONG_ID, "Allocation id", pk=True, rule="ALLOC-<payment_id>-NN"),
    col("payment_id", ID, "Payment", fk="payment.payment_id"),
    col("invoice_line_id", LONG_ID, "Charge line paid", fk="invoice_line.invoice_line_id"),
    col("amount_paise", BigInteger, "Amount applied; negative when an allocation is reversed", unit="paise",
        rule="<> 0"),
    col("allocated_on", Date, "Date applied"),
    CheckConstraint("amount_paise <> 0", name="amount_nonzero"),
    Index("ix_payment_allocation_payment_id", "payment_id"),
    Index("ix_payment_allocation_line_id", "invoice_line_id"),
    comment="PaymentAllocation: bridge Payment N:M InvoiceLine. Reversals are negative rows, never deletes.")

refund = table(
    "refund",
    col("refund_id", ID, "Refund id", pk=True, rule="REF-YYYY-NNNNNN"),
    col("student_id", ID, "Student", fk="student.student_id"),
    col("invoice_id", ID, "Invoice the refund relates to", null=True, fk="invoice.invoice_id"),
    col("payment_id", ID, "Payment the money goes back against", null=True, fk="payment.payment_id"),
    col("amount_paise", BigInteger, "Amount returned", unit="paise", rule="> 0 and <= net paid"),
    col("reason", String(14), "Why", allowed=REFUND_REASONS),
    col("status", String(10), "Current lifecycle state", allowed=REFUND_STATUSES),
    col("approved_on", Date, "Approval date"),
    col("paid_on", Date, "Date the money was returned", null=True, rule=">= approved_on"),
    CheckConstraint("amount_paise > 0", name="amount_positive"),
    CheckConstraint("paid_on IS NULL OR paid_on >= approved_on", name="dates"),
    Index("ix_refund_student_id", "student_id"),
    comment="Refund: money returned to a student.")

# ----------------------------------------------------------------------------------------- derived
ledger_entry = table(
    "ledger_entry",
    col("entry_id", ID, "Ledger entry id", pk=True, rule="LED-NNNNNNN"),
    col("student_id", ID, "Student", fk="student.student_id"),
    col("entry_type", String(12), "Kind of movement", allowed=LEDGER_TYPES),
    col("amount_paise", BigInteger, "Signed amount; positive increases what the student owes", unit="paise"),
    col("posted_on", Date, "Posting date"),
    col("source_type", String(20), "Table the movement came from"),
    col("source_id", LONG_ID, "Primary key of the source row"),
    Index("ix_ledger_entry_student_posted", "student_id", "posted_on"),
    comment="LedgerEntry: append-only. A student's balance is the sum of their entries.")

student_balance = table(
    "student_balance",
    col("student_id", ID, "Student", pk=True, fk="student.student_id"),
    col("charged_paise", BigInteger, "Sum of CHARGE and LATE_FEE entries", unit="paise"),
    col("credits_paise", BigInteger, "Sum of WAIVER, SCHOLARSHIP and ADJUSTMENT entries (negative)",
        unit="paise"),
    col("paid_paise", BigInteger, "Sum of PAYMENT entries (negative)", unit="paise"),
    col("refunded_paise", BigInteger, "Sum of REFUND entries", unit="paise"),
    col("balance_paise", BigInteger, "Stated balance; positive means the student owes", unit="paise",
        rule="= sum(ledger_entry.amount_paise)"),
    col("as_of", Date, "Date the balance is stated as of"),
    comment="StudentBalance: the stated figure, checked against the ledger. 1:1 with Student.")

event = table(
    "event",
    col("event_id", ID, "Event id", pk=True, rule="EVT-NNNNNNN"),
    col("entity_type", String(20), "Kind of entity", allowed=ENTITY_TYPES),
    col("entity_id", LONG_ID, "Primary key of the entity"),
    col("from_status", String(20), "Previous state; empty on creation", null=True),
    col("to_status", String(20), "New state"),
    col("occurred_on", Date, "Date of the change"),
    col("actor", String(40), "SYSTEM or the app_user_id that caused it"),
    Index("ix_event_entity", "entity_type", "entity_id"),
    comment="Event: append-only state history. Current status columns are replayable from these rows.")

# ----------------------------------------------------------------------------------------- operational
app_user = table(
    "app_user",
    col("app_user_id", ID, "Login id", pk=True, rule="USR-NNNNNN"),
    col("email", String(80), "Login email", unique=True),
    col("password_hash", String(200), "scrypt hash, never the password"),
    col("role", String(16), "Role", allowed=ROLES),
    col("student_id", ID, "Student the login belongs to (LEARNER)", null=True, fk="student.student_id"),
    col("program_id", ID, "Program the login is limited to (INSTRUCTOR)", null=True,
        fk="program.program_id"),
    col("enabled", Boolean, "Disabled logins are rejected on every request"),
    col("created_at", DateTime(timezone=True), "Creation time (UTC)"),
    CheckConstraint("(role = 'LEARNER') = (student_id IS NOT NULL)", name="learner_has_student"),
    comment="AppUser: a login and its role.")

idempotency_key = table(
    "idempotency_key",
    col("app_user_id", ID, "Caller", pk=True, fk="app_user.app_user_id"),
    col("key", String(80), "Client supplied Idempotency-Key", pk=True),
    col("request_hash", String(64), "SHA-256 of the request body"),
    col("response_json", JSONB, "Stored response replayed on a retry"),
    col("created_at", DateTime(timezone=True), "Creation time (UTC)"),
    comment="IdempotencyKey: a retried write returns the first answer instead of writing twice.")

exception_case = table(
    "exception",
    col("exception_id", ID, "Exception id", pk=True, rule="EXC-NNNNNN"),
    col("exception_type", String(30), "What the detector found", allowed=ISSUE_TYPES),
    col("entity_type", String(20), "Kind of entity", allowed=ENTITY_TYPES),
    col("entity_id", LONG_ID, "Primary key of the entity"),
    col("student_id", ID, "Student", fk="student.student_id"),
    col("expected_paise", BigInteger, "What the rules say the figure should be", null=True, unit="paise"),
    col("found_paise", BigInteger, "What the data holds", null=True, unit="paise"),
    col("recommended_decision", String(24), "Suggested fix", allowed=DECISIONS_EXPECTED),
    col("status", String(10), "Work state", allowed=EXCEPTION_STATUSES),
    col("note", String(400), "Resolution note", null=True),
    col("resolved_by", ID, "Who closed it", null=True, fk="app_user.app_user_id"),
    col("created_at", DateTime(timezone=True), "Creation time (UTC)"),
    col("resolved_at", DateTime(timezone=True), "Resolution time (UTC)", null=True),
    Index("ix_exception_status_type", "status", "exception_type"),
    Index("ix_exception_student_id", "student_id"),
    comment="Exception: detector output, worked by support staff. Never reads ground truth.")

ground_truth = table(
    "ground_truth",
    col("gt_id", ID, "Ground-truth id", pk=True, rule="GT-NNNNNN"),
    col("issue_type", String(30), "The injected anomaly", allowed=ISSUE_TYPES),
    col("entity_type", String(20), "Kind of entity", allowed=ENTITY_TYPES),
    col("entity_id", LONG_ID, "Primary key of the affected entity"),
    col("student_id", ID, "Student"),
    col("expected_decision", String(24), "Expected fix", allowed=DECISIONS_EXPECTED),
    col("expected_value_paise", BigInteger, "Correct figure", null=True, unit="paise"),
    col("details", String(300), "How the case was built"),
    schema="gt",
    comment="Ground truth: known anomalies. Separate schema and folder; never joined into inputs.")

# ----------------------------------------------------------------------------------------- orderings
# Parent first. Generated, exported and loaded in this order.
DATA_TABLES = ["program", "term", "scholarship_scheme", "student", "fee_schedule", "enrollment", "invoice",
               "eligibility", "scholarship", "invoice_line", "payment", "payment_allocation", "refund",
               "ledger_entry", "student_balance", "event"]
OPERATIONAL_TABLES = ["app_user", "idempotency_key", "exception"]
TABLES = {t.name: t for t in metadata.tables.values()}
TABLES["ground_truth"] = ground_truth
TABLES.pop("gt.ground_truth", None)
# Words that must never be a column of an input table (leak guard, spec 6.2 check 9).
LEAK_WORDS = ("issue_type", "ground_truth", "anomaly")
LEAK_PREFIXES = ("expected_",)


def columns(name: str) -> list[str]:
    """Column names of a table in file order."""
    return [c.name for c in TABLES[name].columns]
