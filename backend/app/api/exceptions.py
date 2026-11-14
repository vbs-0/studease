"""The exceptions queue: what the detectors found, and how support staff close each case."""
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.api import txn
from app.api.deps import Conn, CurrentUser, Page, require_role
from app.api.errors import ApiError
from app.domain.calendar import AS_OF

router = APIRouter(tags=["exceptions"])
QUEUE = ("SUPPORT", "PLATFORM_ADMIN")


class Resolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["RESOLVED", "DISMISSED"]
    note: str = Field(min_length=1, max_length=400)


@router.get("/exceptions", dependencies=[require_role(*QUEUE)])
def list_exceptions(conn: Conn, page: Annotated[Page, Depends()],
                    status: Annotated[Literal["OPEN", "RESOLVED", "DISMISSED"] | None, Query()] = None,
                    exception_type: Annotated[str | None, Query(max_length=30)] = None,
                    student_id: Annotated[str | None, Query(pattern=r"^STU-\d{6}$")] = None):
    rows = conn.execute(text("""
        SELECT * FROM exception
        WHERE (CAST(:after AS text) IS NULL OR exception_id > :after)
          AND (CAST(:st AS text) IS NULL OR status = :st) AND (CAST(:t AS text) IS NULL OR exception_type = :t)
          AND (CAST(:s AS text) IS NULL OR student_id = :s)
        ORDER BY exception_id LIMIT :n"""),
        {"after": page.after, "st": status, "t": exception_type, "s": student_id, "n": page.limit + 1}).mappings().all()
    counts = {r[0]: r[1] for r in conn.execute(text("SELECT status, count(*) FROM exception GROUP BY status"))}
    types = {r[0]: r[1] for r in conn.execute(text(
        "SELECT exception_type, count(*) FROM exception WHERE (CAST(:st AS text) IS NULL OR status = :st) GROUP BY 1 ORDER BY 2 DESC"), {"st": status})}
    return {**page.wrap([dict(r) for r in rows], "exception_id"), "counts": counts, "types": types}


@router.post("/exceptions/{exception_id}/resolve", dependencies=[require_role("SUPPORT")])
def resolve(exception_id: str, body: Resolve, conn: Conn, user: CurrentUser):
    if not re.fullmatch(r"EXC-\d{6}", exception_id):
        raise ApiError(404, "NOT_FOUND", "No such exception.")
    c = txn.begin_write(conn)
    row = conn.execute(text("SELECT status FROM exception WHERE exception_id = :e FOR UPDATE"),
                       {"e": exception_id}).mappings().first()
    if row is None:
        raise ApiError(404, "NOT_FOUND", "No such exception.")
    if row["status"] != "OPEN":
        raise ApiError(409, "ALREADY_CLOSED", f"This exception is already {row['status']}.")
    conn.execute(text("UPDATE exception SET status = :s, note = :n, resolved_by = :u, resolved_at = now()"
                      " WHERE exception_id = :e"),
                 {"s": body.status, "n": body.note, "u": user.app_user_id, "e": exception_id})
    txn.add_event(conn, c, "exception", exception_id, "OPEN", body.status, AS_OF, user.app_user_id)
    conn.commit()
    return {"exception_id": exception_id, "status": body.status}
