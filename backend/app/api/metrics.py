"""Headline figures, data-quality reports and health checks."""
import json
from pathlib import Path

from fastapi import APIRouter
from sqlalchemy import text

from app.api.deps import FINANCE, Conn, require_role
from app.api.errors import ApiError
from app.config import settings
from app.domain.calendar import AS_OF

router = APIRouter(tags=["metrics"])
REPORTS = Path(__file__).resolve().parents[3] / "reports"


@router.get("/metrics/overview", dependencies=[require_role(*FINANCE)])
def overview(conn: Conn):
    one = conn.execute(text("""
        SELECT (SELECT count(*) FROM student) AS students,
               (SELECT count(*) FROM invoice) AS invoices,
               (SELECT count(*) FROM payment) AS payments,
               (SELECT count(*) FROM scholarship) AS scholarships,
               coalesce(sum(charged_paise), 0) AS charged_paise, coalesce(sum(credits_paise), 0) AS credits_paise,
               coalesce(sum(-paid_paise), 0) AS paid_paise, coalesce(sum(refunded_paise), 0) AS refunded_paise,
               coalesce(sum(balance_paise) FILTER (WHERE balance_paise > 0), 0) AS owed_paise,
               coalesce(-sum(balance_paise) FILTER (WHERE balance_paise < 0), 0) AS credit_held_paise,
               (SELECT count(*) FROM exception WHERE status = 'OPEN') AS open_exceptions
        FROM student_balance""")).mappings().one()
    by_status = {r[0]: r[1] for r in conn.execute(text("SELECT status, count(*) FROM invoice GROUP BY status"))}
    by_term = conn.execute(text("""
        SELECT t.term_id, t.term_name, count(i.invoice_id) AS invoices,
               coalesce(sum(i.total_paise), 0) AS net_billed_paise
        FROM term t LEFT JOIN invoice i USING (term_id) GROUP BY t.term_id ORDER BY t.start_date""")).mappings().all()
    by_program = conn.execute(text("""
        SELECT p.program_id, p.name, count(s.student_id) AS students,
               coalesce(sum(b.balance_paise), 0) AS balance_paise
        FROM program p LEFT JOIN student s USING (program_id) LEFT JOIN student_balance b USING (student_id)
        GROUP BY p.program_id ORDER BY p.program_id""")).mappings().all()
    by_month = conn.execute(text("""
        SELECT to_char(date_trunc('month', posted_on), 'YYYY-MM') AS month,
               coalesce(sum(amount_paise) FILTER (WHERE entry_type IN ('CHARGE', 'LATE_FEE')), 0) AS charged_paise,
               coalesce(-sum(amount_paise) FILTER (WHERE entry_type = 'PAYMENT'), 0) AS paid_paise,
               coalesce(sum(amount_paise) FILTER (WHERE entry_type = 'REFUND'), 0) AS refunded_paise
        FROM ledger_entry GROUP BY 1 ORDER BY 1""")).mappings().all()
    by_type = {r[0]: r[1] for r in conn.execute(text(
        "SELECT exception_type, count(*) FROM exception WHERE status = 'OPEN' GROUP BY exception_type"))}
    return {"as_of": AS_OF, **dict(one), "invoice_status": by_status, "open_by_type": by_type,
            "by_month": [dict(r) for r in by_month], "by_term": [dict(r) for r in by_term], "by_program": [dict(r) for r in by_program]}


@router.get("/quality", dependencies=[require_role("PLATFORM_ADMIN")])
def quality():
    """The reports the generator and the evaluation wrote to reports/<scale>/ (committed with the repository)."""
    folder = REPORTS / settings.data_scale
    out = {"scale": settings.data_scale}
    for key, name in (("validation", "validation_summary"), ("evaluation", "evaluation"), ("repro", "repro")):
        path = folder / f"{name}.json"
        out[key] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if all(out[k] is None for k in ("validation", "evaluation", "repro")):
        raise ApiError(404, "NOT_FOUND", "No quality reports found for this data scale.")
    return out


@router.get("/healthz")
def healthz():
    return {"status": "ok"}


@router.get("/readyz")
def readyz(conn: Conn):
    conn.execute(text("SELECT 1"))
    return {"status": "ready"}
