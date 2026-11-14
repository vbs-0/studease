"""Seed the demo logins: one per role, passwords from DEMO_PASSWORD (never committed)."""
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app import ids, security
from app.config import settings

DEMO = [("learner", "LEARNER"), ("instructor", "INSTRUCTOR"), ("academic", "ACADEMIC_ADMIN"),
        ("support", "SUPPORT"), ("admin", "PLATFORM_ADMIN")]


def seed_users(engine: Engine, password: str | None = None) -> list[dict]:
    """Insert the five demo users (replacing any existing ones). The learner is the first student with an invoice and
    a payment; the instructor is limited to that student's program."""
    password = password or settings.demo_password
    pw = security.hash_password(password)
    with engine.begin() as conn:
        sid, program = conn.execute(text("""
            SELECT s.student_id, s.program_id FROM student s
            WHERE EXISTS (SELECT 1 FROM payment p WHERE p.student_id = s.student_id)
              AND EXISTS (SELECT 1 FROM refund r WHERE r.student_id = s.student_id)
            ORDER BY s.student_id LIMIT 1""")).first() or conn.execute(text(
                "SELECT student_id, program_id FROM student ORDER BY student_id LIMIT 1")).first()
        conn.execute(text("DELETE FROM app_user"))
        users = []
        for n, (name, role) in enumerate(DEMO, 1):
            user = {"app_user_id": ids.user_id(n), "email": f"{name}@example.edu", "password_hash": pw,
                    "role": role, "student_id": sid if role == "LEARNER" else None,
                    "program_id": program if role == "INSTRUCTOR" else None, "enabled": True,
                    "created_at": datetime.now(UTC)}
            conn.execute(text("INSERT INTO app_user VALUES (:app_user_id, :email, :password_hash, :role, :student_id,"
                              " :program_id, :enabled, :created_at)"), user)
            users.append({k: user[k] for k in ("email", "role", "student_id", "program_id")})
    return users
