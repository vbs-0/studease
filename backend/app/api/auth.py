"""Sign-in, identity and password reset (S-3, S-4, S-7, S-23)."""
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app import mail, security
from app.api.deps import Conn, CurrentUser
from app.api.errors import ApiError
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=80)
    password: str = Field(min_length=1, max_length=128)


class Forgot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(max_length=80)


class Reset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(max_length=1000)
    new_password: str = Field(min_length=12, max_length=128)


def _by_email(conn, email: str):
    return conn.execute(text("SELECT * FROM app_user WHERE lower(email) = :e AND enabled"),
                        {"e": email.strip().lower()}).mappings().first()


@router.post("/login")
def login(body: Login, conn: Conn):
    user = _by_email(conn, body.email)
    # Unknown email and wrong password give the same answer (S-4). Throttling and timing equalisation are
    # deferred by decision (docs/architecture.md section 12); a test pins that they are absent.
    if user is None or not security.verify_password(body.password, user["password_hash"]):
        raise ApiError(401, "BAD_CREDENTIALS", "Email or password is incorrect.")
    return {"token": security.make_token(user), "role": user["role"], "email": user["email"],
            "student_id": user["student_id"], "program_id": user["program_id"]}


@router.get("/me")
def me(user: CurrentUser):
    return {"app_user_id": user.app_user_id, "email": user.email, "role": user.role,
            "student_id": user.student_id, "program_id": user.program_id}


@router.post("/forgot", status_code=202)
def forgot(body: Forgot, conn: Conn, tasks: BackgroundTasks):
    """Always 202 with the same body, so the answer never reveals whether an email has an account."""
    user = _by_email(conn, body.email)
    if user is not None:
        link = f"{settings.app_url}/reset?token={security.make_reset_token(user)}"
        tasks.add_task(mail.send, user["email"], "Reset your StudEase password",
                       f"Open this link within {security.RESET_MINUTES} minutes to choose a new password:\n\n"
                       f"{link}\n\nIf you did not ask for this, ignore this message.")
    return {"message": "If that email has an account, a reset link is on its way."}


@router.post("/reset")
def reset(body: Reset, conn: Conn):
    claims = security.read_reset_token(body.token)
    user = conn.execute(text("SELECT * FROM app_user WHERE app_user_id = :u AND enabled"),
                        {"u": claims["sub"]}).mappings().first() if claims else None
    if user is None or not security.reset_token_matches(claims, user):
        raise ApiError(400, "BAD_RESET_LINK", "This reset link is invalid or has already been used.")
    conn.execute(text("UPDATE app_user SET password_hash = :h WHERE app_user_id = :u"),
                 {"h": security.hash_password(body.new_password), "u": user["app_user_id"]})
    conn.commit()
    return {"message": "Password changed. You can sign in now."}
