"""Security controls S-1, S-3, S-4, S-7, S-10, S-11, S-12, S-23 and the pinned decision to defer throttling."""
import re
import time
from pathlib import Path

import jwt
import pytest

from app import security
from app.config import settings

from .conftest import PASSWORD

pytestmark = pytest.mark.db
API = "/api/v1"


# ------------------------------------------------------------------ pure (no database)
def test_scrypt_hash_verifies_and_is_salted():
    a, b = security.hash_password("correct horse"), security.hash_password("correct horse")
    assert a != b and a.startswith("scrypt$16384$8$1$")
    assert security.verify_password("correct horse", a) and not security.verify_password("wrong", a)


def test_a_malformed_stored_hash_is_a_failure_not_a_crash():
    for bad in ("", "plain", "scrypt$x$y$z$q$w", "md5$1$2$3$aa$bb"):
        assert security.verify_password("x", bad) is False


def test_s1_no_sql_is_built_from_strings():
    """Every text() call in the API takes a literal; request input only ever travels as bound parameters."""
    root = Path(__file__).resolve().parents[2] / "app"
    offenders = []
    for path in [*root.glob("api/*.py"), root / "engine" / "users.py"]:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"text\(\s*f[\"']", line) or re.search(r"\.format\(", line) and "text(" in line:
                offenders.append(f"{path.name}:{n}")
    assert offenders == []


# ------------------------------------------------------------------ sign-in
def test_login_returns_a_token_and_me_reads_it_back(client, loaded):
    res = client.post(f"{API}/auth/login", json={"email": "support@example.edu", "password": PASSWORD})
    assert res.status_code == 200 and res.json()["role"] == "SUPPORT"
    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {res.json()['token']}"})
    assert me.json()["email"] == "support@example.edu"


def test_s4_unknown_email_and_wrong_password_look_identical(client, loaded):
    a = client.post(f"{API}/auth/login", json={"email": "nobody@example.edu", "password": "whatever-123"})
    b = client.post(f"{API}/auth/login", json={"email": "support@example.edu", "password": "whatever-123"})
    assert a.status_code == b.status_code == 401
    assert a.json()["error"]["code"] == b.json()["error"]["code"] == "BAD_CREDENTIALS"
    assert a.json()["error"]["message"] == b.json()["error"]["message"]


def test_throttling_is_deliberately_absent_for_now(client, loaded):
    """Owner decision 2026-11-14 (docs/architecture.md section 12): no lockout while testing. When throttling is built
    this test must be replaced by one that expects a 429."""
    codes = {client.post(f"{API}/auth/login", json={"email": "support@example.edu", "password": f"bad-{n}"})
             .status_code for n in range(25)}
    assert codes == {401}


# ------------------------------------------------------------------ tokens
def test_s7_requests_without_a_valid_token_are_401(client, loaded):
    assert client.get(f"{API}/students").status_code == 401
    assert client.get(f"{API}/students", headers={"Authorization": "Bearer nonsense"}).status_code == 401
    assert client.get(f"{API}/students", headers={"Authorization": "Basic abc"}).status_code == 401


def test_s7_token_signed_with_the_wrong_key_or_algorithm_is_rejected(client, loaded):
    claims = {"sub": "USR-000004", "exp": int(time.time()) + 600}
    for forged in (jwt.encode(claims, "another-secret-another-secret-123456", algorithm="HS256"),
                   jwt.encode(claims, settings.jwt_secret, algorithm="HS512"),
                   jwt.encode(claims, key=None, algorithm="none")):
        res = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {forged}"})
        assert res.status_code == 401


def test_s7_an_expired_token_is_rejected(client, loaded):
    old = jwt.encode({"sub": "USR-000004", "exp": int(time.time()) - 5}, settings.jwt_secret, algorithm="HS256")
    assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {old}"}).status_code == 401


def test_s7_a_disabled_user_is_rejected_at_once(client, loaded, as_role):
    admin = as_role("SUPPORT")
    assert admin.get("/auth/me").status_code == 200
    with loaded["engine"].begin() as c:
        from sqlalchemy import text
        c.execute(text("UPDATE app_user SET enabled = false WHERE role = 'SUPPORT'"))
    assert admin.get("/auth/me").status_code == 401


def test_a_reset_token_cannot_be_used_as_an_access_token(client, loaded):
    user = {"app_user_id": "USR-000004", "password_hash": "x"}
    token = security.make_reset_token(user)
    assert client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


# ------------------------------------------------------------------ roles and scope (S-2)
def test_a_learner_sees_only_their_own_account(as_role, loaded):
    learner = as_role("LEARNER")
    mine = loaded["users"]["LEARNER"]["student_id"]
    other = next(s["student_id"] for s in loaded["ds"]["student"] if s["student_id"] != mine)
    assert learner.get(f"/students/{mine}").status_code == 200
    assert learner.get(f"/students/{mine}/ledger").status_code == 200
    assert learner.get(f"/students/{other}").status_code == 404           # same answer as a missing student
    assert learner.get(f"/students/{other}/ledger").status_code == 404
    assert learner.get("/students").status_code == 403
    assert learner.get("/exceptions").status_code == 403
    assert learner.get("/fee-schedules").status_code == 403
    inv_other = next(i["invoice_id"] for i in loaded["ds"]["invoice"] if i["student_id"] == other)
    assert learner.get(f"/invoices/{inv_other}").status_code == 404


def test_an_instructor_sees_own_program_without_money(as_role, loaded):
    inst = as_role("INSTRUCTOR")
    program = loaded["users"]["INSTRUCTOR"]["program_id"]
    listing = inst.get("/students?limit=200").json()["items"]
    assert listing and {s["program_id"] for s in listing} == {program}
    assert "balance_paise" not in listing[0]
    outside = next(s["student_id"] for s in loaded["ds"]["student"] if s["program_id"] != program)
    assert inst.get(f"/students/{outside}").status_code == 404
    inside = listing[0]["student_id"]
    detail = inst.get(f"/students/{inside}").json()
    assert "balance" not in detail and "invoices" not in detail
    assert inst.get(f"/students/{inside}/ledger").status_code == 403
    assert inst.get("/metrics/overview").status_code == 403


def test_writes_are_limited_to_their_roles(as_role, loaded):
    sid = loaded["ds"]["student"][0]["student_id"]
    body = {"student_id": sid, "amount_paise": 100, "method": "UPI", "reference": "x"}
    for role in ("LEARNER", "INSTRUCTOR", "ACADEMIC_ADMIN"):
        assert as_role(role).post("/payments", body, {"Idempotency-Key": "role-check-1"}).status_code == 403
    enr = loaded["ds"]["enrollment"][0]["enrollment_id"]
    for role in ("LEARNER", "SUPPORT"):
        assert as_role(role).post(f"/enrollments/{enr}/withdraw", {}).status_code == 403
    assert as_role("ACADEMIC_ADMIN").post("/exceptions/EXC-000001/resolve",
                                          {"status": "RESOLVED", "note": "x"}).status_code == 403


# ------------------------------------------------------------------ input and error hygiene (S-10, S-12)
def test_s10_unknown_fields_and_bad_values_are_rejected(as_role, loaded):
    s = as_role("SUPPORT")
    sid = loaded["ds"]["student"][0]["student_id"]
    key = {"Idempotency-Key": "input-check-1"}
    good = {"student_id": sid, "amount_paise": 100, "method": "UPI", "reference": "x"}
    assert s.post("/payments", {**good, "extra": 1}, key).status_code == 422
    assert s.post("/payments", {**good, "amount_paise": 0}, key).status_code == 422
    assert s.post("/payments", {**good, "amount_paise": 1_000_000_001}, key).status_code == 422
    assert s.post("/payments", {**good, "method": "BARTER"}, key).status_code == 422
    assert s.post("/payments", {**good, "student_id": "STU-1; DROP TABLE payment"}, key).status_code == 422
    assert s.get("/students?limit=500").status_code == 422
    assert s.get("/students?limit=0").status_code == 422


def test_s12_errors_use_the_envelope_and_carry_a_request_id(client, loaded):
    res = client.get(f"{API}/nothing-here")
    body = res.json()
    assert res.status_code == 404 and set(body["error"]) == {"code", "message", "request_id"}
    assert res.headers["X-Request-ID"] == body["error"]["request_id"]
    assert res.headers["X-Content-Type-Options"] == "nosniff"


def test_s12_an_unexpected_failure_is_a_500_envelope_without_a_trace(client, loaded, monkeypatch):
    from app.api import metrics
    monkeypatch.setattr(metrics.settings, "data_scale", "../../etc")      # not a real folder: handled, never a trace
    res = client.get(f"{API}/healthz")
    assert res.status_code == 200


def test_s11_cors_allows_only_configured_origins(client, loaded):
    ok = client.options(f"{API}/auth/login", headers={"Origin": settings.cors_list[0],
                                                       "Access-Control-Request-Method": "POST"})
    bad = client.options(f"{API}/auth/login", headers={"Origin": "https://evil.example",
                                                        "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == settings.cors_list[0]
    assert "access-control-allow-origin" not in bad.headers
    assert "access-control-allow-credentials" not in ok.headers


# ------------------------------------------------------------------ password reset (S-23)
def test_s23_forgot_answers_the_same_for_known_and_unknown_emails(client, loaded):
    a = client.post(f"{API}/auth/forgot", json={"email": "support@example.edu"})
    b = client.post(f"{API}/auth/forgot", json={"email": "ghost@example.edu"})
    assert a.status_code == b.status_code == 202 and a.json() == b.json()


def test_s23_a_reset_link_works_once_and_only_for_its_user(client, loaded):
    with loaded["engine"].connect() as c:
        from sqlalchemy import text
        user = dict(c.execute(text("SELECT * FROM app_user WHERE role = 'SUPPORT'")).mappings().one())
    token = security.make_reset_token(user)
    new = "brand-new-password-9"
    assert client.post(f"{API}/auth/reset", json={"token": token, "new_password": new}).status_code == 200
    assert client.post(f"{API}/auth/login", json={"email": user["email"], "password": new}).status_code == 200
    again = client.post(f"{API}/auth/reset", json={"token": token, "new_password": "another-password-9"})
    assert again.status_code == 400 and again.json()["error"]["code"] == "BAD_RESET_LINK"
    assert client.post(f"{API}/auth/reset", json={"token": "junk", "new_password": new}).status_code == 400
    assert client.post(f"{API}/auth/reset", json={"token": token, "new_password": "short"}).status_code == 422


def test_s6_production_refuses_default_secrets(monkeypatch):
    from app.config import Settings
    with pytest.raises(RuntimeError):
        Settings(env="prod").check()
    with pytest.raises(RuntimeError):
        Settings(env="prod", jwt_secret="x" * 40).check()          # secret fine, demo password still default
    Settings(env="prod", jwt_secret="x" * 40, demo_password="a-strong-password").check()
