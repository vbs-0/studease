"""Reference data: programs, terms, fee schedules, scholarship schemes, awards and eligibility decisions."""
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from app.api.deps import FINANCE, Conn, Page, require_role

router = APIRouter(tags=["catalog"], dependencies=[require_role(*FINANCE)])

Opt = Annotated[str | None, Query(max_length=40)]


@router.get("/programs")
def programs(conn: Conn):
    return {"items": [dict(r) for r in conn.execute(text(
        "SELECT p.*, (SELECT count(*) FROM student s WHERE s.program_id = p.program_id) AS students"
        " FROM program p ORDER BY program_id")).mappings()]}


@router.get("/terms")
def terms(conn: Conn):
    return {"items": [dict(r) for r in conn.execute(text("SELECT * FROM term ORDER BY start_date")).mappings()]}


@router.get("/fee-schedules")
def fee_schedules(conn: Conn, program_id: Opt = None, term_id: Opt = None):
    rows = conn.execute(text("""
        SELECT * FROM fee_schedule
        WHERE (CAST(:p AS text) IS NULL OR program_id = :p) AND (CAST(:t AS text) IS NULL OR term_id = :t)
        ORDER BY program_id, term_id, fee_type, version LIMIT 1000"""), {"p": program_id, "t": term_id}).mappings()
    return {"items": [dict(r) for r in rows]}


@router.get("/scholarship-schemes")
def schemes(conn: Conn):
    return {"items": [dict(r) for r in conn.execute(text(
        "SELECT * FROM scholarship_scheme ORDER BY priority")).mappings()]}


@router.get("/scholarships/summary")
def scholarship_summary(conn: Conn):
    rows = conn.execute(text("""SELECT c.scheme_code, c.name, count(s.scholarship_id) AS awards,
                                       coalesce(sum(s.amount_paise), 0) AS awarded_paise
                                FROM scholarship_scheme c LEFT JOIN scholarship s USING (scheme_code)
                                GROUP BY c.scheme_code, c.name, c.priority ORDER BY c.priority""")).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.get("/scholarships")
def scholarships(conn: Conn, page: Annotated[Page, Depends()], student_id: Opt = None, scheme_code: Opt = None,
                 status: Opt = None):
    rows = conn.execute(text("""
        SELECT * FROM scholarship
        WHERE (CAST(:after AS text) IS NULL OR scholarship_id > :after)
          AND (CAST(:s AS text) IS NULL OR student_id = :s) AND (CAST(:c AS text) IS NULL OR scheme_code = :c)
          AND (CAST(:st AS text) IS NULL OR status = :st)
        ORDER BY scholarship_id LIMIT :n"""),
        {"after": page.after, "s": student_id, "c": scheme_code, "st": status, "n": page.limit + 1}).mappings().all()
    return page.wrap([dict(r) for r in rows], "scholarship_id")


@router.get("/eligibility")
def eligibility(conn: Conn, page: Annotated[Page, Depends()], student_id: Opt = None, decision: Opt = None,
                scheme_code: Opt = None):
    rows = conn.execute(text("""
        SELECT * FROM eligibility
        WHERE (CAST(:after AS text) IS NULL OR eligibility_id > :after)
          AND (CAST(:s AS text) IS NULL OR student_id = :s) AND (CAST(:d AS text) IS NULL OR decision = :d)
          AND (CAST(:c AS text) IS NULL OR scheme_code = :c)
        ORDER BY eligibility_id LIMIT :n"""),
        {"after": page.after, "s": student_id, "d": decision, "c": scheme_code, "n": page.limit + 1}).mappings().all()
    return page.wrap([dict(r) for r in rows], "eligibility_id")
