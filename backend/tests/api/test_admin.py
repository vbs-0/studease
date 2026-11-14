"""Staff data entry and administration: fee versions, adding students, profiles, assigning awards, user accounts."""
import pytest
from sqlalchemy import text

from .test_learner import books, signed_up

pytestmark = pytest.mark.db

FEE = {"program_id": "PRG-01", "term_id": "TERM-2026-FALL", "fee_type": "LAB", "applies_to": "ALL", "amount_paise": 1_600_000,
       "effective_from": "2026-09-01", "scholarship_eligible": True}
STUDENT = {"full_name": "Staff Added", "program_id": "PRG-01", "residency": "DOMESTIC", "gpa": 9.2, "income_band": "LOW"}


def test_a_new_fee_version_closes_the_previous_one(as_role, loaded):
    admin = as_role("ACADEMIC_ADMIN")
    before = [f for f in admin.get("/fee-schedules?program_id=PRG-01&term_id=TERM-2026-FALL").json()["items"] if f["fee_type"] == "LAB"]
    res = admin.post("/fee-schedules", FEE)
    assert res.status_code == 201, res.text
    new = res.json()
    assert new["version"] == before[-1]["version"] + 1 and new["fee_schedule_id"].endswith(f"-V{new['version']}")
    after = {f["version"]: f for f in admin.get("/fee-schedules?program_id=PRG-01&term_id=TERM-2026-FALL").json()["items"] if f["fee_type"] == "LAB"}
    assert after[before[-1]["version"]]["effective_to"] == "2026-08-31" and after[new["version"]]["effective_to"] is None


def test_fee_versions_must_move_forward_and_keep_their_audience(as_role, loaded):
    admin = as_role("ACADEMIC_ADMIN")
    assert admin.post("/fee-schedules", {**FEE, "effective_from": "2020-01-01"}).status_code == 409
    assert admin.post("/fee-schedules", {**FEE, "applies_to": "HOSTEL"}).status_code == 409
    assert admin.post("/fee-schedules", {**FEE, "amount_paise": 0}).status_code == 422
    assert admin.post("/fee-schedules", {**FEE, "program_id": "PRG-99"}).status_code == 404
    assert as_role("SUPPORT").post("/fee-schedules", FEE).status_code == 403
    assert as_role("LEARNER").post("/fee-schedules", FEE).status_code == 403


def test_a_new_fee_is_billed_to_the_next_enrolment_only(client, loaded, as_role):
    as_role("ACADEMIC_ADMIN").post("/fee-schedules", {**FEE, "effective_from": "2026-08-01", "amount_paise": 2_000_000})
    s = signed_up(client)
    fall = s.get("/me/enrollable").json()["items"][0]
    assert any(ln["amount_paise"] == 2_000_000 for ln in fall["lines"])


def test_staff_add_a_student_with_an_optional_login(client, loaded, as_role):
    support = as_role("SUPPORT")
    res = support.post("/students", {**STUDENT, "login_email": "staff.added@mail.test", "login_password": "a-long-password-1"})
    assert res.status_code == 201, res.text
    sid = res.json()["student_id"]
    assert client.post("/api/v1/auth/login", json={"email": "staff.added@mail.test", "password": "a-long-password-1"}).status_code == 200
    assert support.post("/students", {**STUDENT, "login_email": "x@mail.test"}).status_code == 422             # email without password
    assert support.post("/students", {**STUDENT, "login_email": "staff.added@mail.test", "login_password": "a-long-password-1"}).status_code == 409
    assert support.get(f"/students/{sid}").json()["balance"]["stated"] == 0
    assert as_role("INSTRUCTOR").post("/students", STUDENT).status_code == 403
    assert as_role("LEARNER").post("/students", STUDENT).status_code == 403


def test_profiles_staff_can_change_everything_learners_only_name_and_housing(client, loaded, as_role):
    s = signed_up(client)
    sid = s.user["student_id"]
    assert as_role("SUPPORT").post(f"/students/{sid}/profile", {"gpa": 6.5, "income_band": "HIGH"}).json()["changed"] == ["gpa", "income_band"]
    assert s.post("/me/profile", {"full_name": "Renamed Person", "hostel_resident": True}).status_code == 200
    assert s.post("/me/profile", {"gpa": 10}).status_code == 422                       # a learner cannot raise their own GPA
    assert s.post("/me/profile", {}).status_code == 422
    row = as_role("SUPPORT").get(f"/students/{sid}").json()["student"]
    assert row["gpa"] == 6.5 and row["full_name"] == "Renamed Person" and row["hostel_resident"] is True
    assert as_role("SUPPORT").post("/students/STU-999999/profile", {"gpa": 5}).status_code == 404
    assert as_role("INSTRUCTOR").post(f"/students/{sid}/profile", {"gpa": 5}).status_code == 403


def test_assigning_a_scholarship_applies_the_rules_and_keeps_the_books(client, loaded, as_role):
    s = signed_up(client, gpa=7.0, income_band="LOW", sports_quota=False)
    sid = s.user["student_id"]
    s.post("/me/enroll", {"term_id": "TERM-2026-FALL"})
    admin = as_role("ACADEMIC_ADMIN")
    refused = admin.post(f"/students/{sid}/scholarships", {"term_id": "TERM-2026-FALL", "scheme_code": "MERIT_GOLD"})
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "NOT_ELIGIBLE"       # staff cannot waive the criteria
    ok = admin.post(f"/students/{sid}/scholarships", {"term_id": "TERM-2026-FALL", "scheme_code": "NEED_BASED"})
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["scholarship"]["amount_paise"] <= body["scholarship"]["eligible_fees_paise"]
    stated, led, docs = books(loaded["engine"], sid)
    assert stated == led == docs == body["invoice"]["total_paise"]
    again = admin.post(f"/students/{sid}/scholarships", {"term_id": "TERM-2026-FALL", "scheme_code": "NEED_BASED"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "ALREADY_AWARDED"
    assert as_role("SUPPORT").post(f"/students/{sid}/scholarships", {"term_id": "TERM-2026-FALL", "scheme_code": "NEED_BASED"}).status_code == 403


def test_assigning_requires_an_enrolment(client, loaded, as_role):
    s = signed_up(client)
    res = as_role("ACADEMIC_ADMIN").post(f"/students/{s.user['student_id']}/scholarships", {"term_id": "TERM-2026-FALL", "scheme_code": "NEED_BASED"})
    assert res.status_code == 409 and res.json()["error"]["code"] == "NOT_ENROLLED"


def test_admin_user_management(client, loaded, as_role):
    admin = as_role("PLATFORM_ADMIN")
    users = admin.get("/admin/users").json()["items"]
    assert len(users) == 5 and "password_hash" not in users[0]
    ok = admin.post("/admin/users", {"email": "new.support@mail.test", "password": "a-long-password-1", "role": "SUPPORT"})
    assert ok.status_code == 201 and client.post("/api/v1/auth/login", json={"email": "new.support@mail.test", "password": "a-long-password-1"}).status_code == 200
    assert admin.post("/admin/users", {"email": "l@mail.test", "password": "a-long-password-1", "role": "LEARNER"}).status_code == 422
    assert admin.post("/admin/users", {"email": "i@mail.test", "password": "a-long-password-1", "role": "INSTRUCTOR"}).status_code == 422
    assert admin.post("/admin/users", {"email": "s@mail.test", "password": "a-long-password-1", "role": "SUPPORT", "program_id": "PRG-01"}).status_code == 422
    assert admin.post("/admin/users", {"email": "new.support@mail.test", "password": "a-long-password-1", "role": "SUPPORT"}).status_code == 409
    uid = ok.json()["app_user_id"]
    assert admin.post(f"/admin/users/{uid}/enabled", {"enabled": False}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "new.support@mail.test", "password": "a-long-password-1"}).status_code == 401
    me = admin.get("/auth/me").json()["app_user_id"]
    assert admin.post(f"/admin/users/{me}/enabled", {"enabled": False}).status_code == 409
    assert admin.post("/admin/users/USR-999999/enabled", {"enabled": True}).status_code == 404
    for role in ("SUPPORT", "ACADEMIC_ADMIN", "INSTRUCTOR", "LEARNER"):
        assert as_role(role).get("/admin/users").status_code == 403


def test_chart_data_endpoints(as_role, loaded):
    ov = as_role("SUPPORT").get("/metrics/overview").json()
    assert ov["by_month"] and {"month", "charged_paise", "paid_paise", "refunded_paise"} <= set(ov["by_month"][0])
    assert sum(m["paid_paise"] for m in ov["by_month"]) == ov["paid_paise"]
    summary = as_role("ACADEMIC_ADMIN").get("/scholarships/summary").json()["items"]
    assert sum(i["awards"] for i in summary) == len(loaded["ds"]["scholarship"])
    ex = as_role("SUPPORT").get("/exceptions?status=OPEN&limit=1").json()
    assert sum(ex["types"].values()) == ex["counts"]["OPEN"]
    with loaded["engine"].connect() as c:
        assert c.execute(text("SELECT count(*) FROM app_user")).scalar() >= 5
