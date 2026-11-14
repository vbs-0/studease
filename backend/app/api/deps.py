"""Shared request dependencies: who is calling (S-7), what they may do (S-2), and paging (S-10)."""
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Query
from sqlalchemy import Connection, text

from app import ids, security
from app.api.errors import ApiError
from app.db import get_conn

Conn = Annotated[Connection, Depends(get_conn)]
STAFF = ("INSTRUCTOR", "ACADEMIC_ADMIN", "SUPPORT", "PLATFORM_ADMIN")
FINANCE = ("ACADEMIC_ADMIN", "SUPPORT", "PLATFORM_ADMIN")     # staff who may see money


@dataclass(frozen=True)
class User:
    app_user_id: str
    email: str
    role: str
    student_id: str | None
    program_id: str | None


def current_user(conn: Conn, authorization: Annotated[str | None, Header()] = None) -> User:
    """Bearer token -> a user row. Role and enabled flag come from the database on every request, so disabling
    a user or changing a role takes effect at once, whatever an old token claims."""
    scheme, _, token = (authorization or "").partition(" ")
    claims = security.read_token(token) if scheme.lower() == "bearer" and token else None
    row = None
    if claims:
        row = conn.execute(text("SELECT app_user_id, email, role, student_id, program_id FROM app_user"
                                " WHERE app_user_id = :u AND enabled"), {"u": claims["sub"]}).mappings().first()
    if row is None:
        raise ApiError(401, "UNAUTHENTICATED", "Sign in again.")
    return User(**row)


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(*roles: str):
    """One place that authorises by role. A learner who is not in the list gets 403 from every staff route."""
    def check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ApiError(403, "FORBIDDEN", "Your role cannot do this.")
        return user
    return Depends(check)


def scope_student(conn: Connection, user: User, student_id: str) -> None:
    """Object-level authorisation. A learner sees only the id in their own token; an instructor only students of
    their program. Anything out of scope answers 404, the same as a missing student, so ids cannot be probed."""
    if not ids.matches("student", student_id):
        raise ApiError(404, "NOT_FOUND", "No such student.")
    if user.role == "LEARNER":
        ok = student_id == user.student_id
    else:
        program = conn.execute(text("SELECT program_id FROM student WHERE student_id = :s"),
                               {"s": student_id}).scalar()
        ok = program is not None and (user.role != "INSTRUCTOR" or program == user.program_id)
    if not ok:
        raise ApiError(404, "NOT_FOUND", "No such student.")


def check_id(table: str, value: str) -> str:
    if not ids.matches(table, value):
        raise ApiError(404, "NOT_FOUND", f"No such {table.replace('_', ' ')}.")
    return value


class Page:
    """Keyset pagination: ?after=<last id>&limit=50. Stable under inserts, constant cost at any depth."""
    def __init__(self, limit: Annotated[int, Query(ge=1, le=200)] = 50,
                 after: Annotated[str | None, Query(max_length=60)] = None):
        self.limit, self.after = limit, after

    def wrap(self, rows: list[dict], key: str) -> dict:
        more = len(rows) > self.limit
        rows = rows[: self.limit]
        return {"items": rows, "next": rows[-1][key] if more and rows else None}
