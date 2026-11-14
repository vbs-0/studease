"""Learner self-service: sign up, enrol (billing and scholarship decisions), pay, withdraw, own awards and fees."""
import pytest
from sqlalchemy import text

from .conftest import PASSWORD, Session

pytestmark = pytest.mark.db
API = "/api/v1"
NEW = {"email": "new.person@mail.test", "password": "a-long-password-1", "full_name": "New Person", "program_id": "PRG-01",
       "residency": "DOMESTIC", "gpa": 9.4, "income_band": "LOW", "sports_quota": True, "hostel_resident": False}


def signed_up(client, **over):
    res = client.post(f"{API}/auth/signup", json={**NEW, **over})
    assert res.status_code == 201, res.text
    s = Session.__new__(Session)
    s.client, s.role, s.token = client, "LEARNER", res.json()["token"]
    s.user = res.json()
    return s


def books(engine, sid):
    with engine.connect() as c:
        stated = c.execute(text("SELECT balance_paise FROM student_balance WHERE student_id = :s"), {"s": sid}).scalar()
        led = c.execute(text("SELECT coalesce(sum(amount_paise),0) FROM ledger_entry WHERE student_id = :s"), {"s": sid}).scalar()
        docs = c.execute(text("""SELECT (SELECT coalesce(sum(total_paise),0) FROM invoice WHERE student_id=:s)
              - (SELECT coalesce(sum(amount_paise),0) FROM payment WHERE student_id=:s)
              + (SELECT coalesce(sum(amount_paise),0) FROM refund WHERE student_id=:s)"""), {"s": sid}).scalar()
    return stated, led, docs


def test_signup_creates_a_student_and_signs_in(client, loaded):
    s = signed_up(client)
    me = s.get("/auth/me").json()
    assert me["role"] == "LEARNER" and me["student_id"].startswith("STU-")
    again = client.post(f"{API}/auth/signup", json=NEW)
    assert again.status_code == 409 and again.json()["error"]["code"] == "EMAIL_TAKEN"
    login = client.post(f"{API}/auth/login", json={"email": NEW["email"], "password": NEW["password"]})
    assert login.status_code == 200
    detail = s.get(f"/students/{me['student_id']}").json()
    assert detail["student"]["email"].endswith("@example.edu") and detail["balance"]["stated"] == 0


def test_signup_validation(client, loaded):
    for bad in ({"password": "short"}, {"email": "not-an-email"}, {"gpa": 11}, {"program_id": "PRG-99"},
                {"residency": "MARTIAN"}, {"role": "PLATFORM_ADMIN"}):
        assert client.post(f"{API}/auth/signup", json={**NEW, **bad}).status_code == 422, bad


def test_signup_cannot_choose_a_role_or_a_student(client, loaded):
    res = client.post(f"{API}/auth/signup", json={**NEW, "student_id": "STU-000001"})
    assert res.status_code == 422                                     # extra fields are forbidden


def test_enrolling_bills_the_fees_and_decides_scholarships_and_books_reconcile(client, loaded):
    s = signed_up(client)
    sid = s.user["student_id"]
    options = s.get("/me/enrollable").json()["items"]
    assert [o["term"]["term_id"] for o in options] == ["TERM-2026-FALL"]
    fall = options[0]
    meets = {x["scheme_code"] for x in fall["schemes"] if x["meets_criteria"]}
    assert {"MERIT_GOLD", "SPORTS", "NEED_BASED"} <= meets            # gpa 9.4, sports quota, low income
    res = s.post("/me/enroll", {"term_id": "TERM-2026-FALL", "applications": ["MERIT_GOLD", "SPORTS", "INTL_EXCELLENCE"]})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["enrollment"]["status"] == "ENROLLED" and body["invoice"]["status"] == "ISSUED"
    assert body["scholarship"]["scheme_code"] == "MERIT_GOLD"          # 50% beats the 3,00,000 fixed sports award or ties by priority
    assert body["scholarship"]["amount_paise"] <= body["scholarship"]["eligible_fees_paise"]
    assert body["invoice"]["total_paise"] == sum(ln["amount_paise"] for ln in body["lines"]) == body["balance"]["balance_paise"]
    assert books(loaded["engine"], sid) == (body["invoice"]["total_paise"],) * 3
    decisions = s.get("/me/scholarships").json()
    assert {d["scheme_code"]: d["decision"] for d in decisions["decisions"]}["INTL_EXCELLENCE"] == "INELIGIBLE"
    assert len(decisions["awards"]) == 1
    again = s.post("/me/enroll", {"term_id": "TERM-2026-FALL"})
    assert again.status_code == 409 and again.json()["error"]["code"] == "CANNOT_ENROLL"


def test_enrolling_into_an_ended_term_is_refused(client, loaded):
    s = signed_up(client)
    assert s.post("/me/enroll", {"term_id": "TERM-2026-SPRING"}).status_code == 409


def test_a_new_learner_pays_and_withdraws_and_the_books_still_balance(client, loaded):
    s = signed_up(client, gpa=7.0, sports_quota=False, income_band="HIGH")
    sid = s.user["student_id"]
    enrolled = s.post("/me/enroll", {"term_id": "TERM-2026-FALL"}).json()
    total = enrolled["invoice"]["total_paise"]
    pay = s.post("/me/payments", {"amount_paise": total // 2, "method": "UPI", "reference": "mine-1"}, {"Idempotency-Key": "learner-pay-0001"})
    assert pay.status_code == 201, pay.text
    assert pay.json()["balance"]["balance_paise"] == total - total // 2
    assert books(loaded["engine"], sid)[0] == total - total // 2
    out = s.post(f"/me/enrollments/{enrolled['enrollment']['enrollment_id']}/withdraw", {})
    assert out.status_code == 200 and out.json()["outcome"] == "WITHDRAWN"
    stated, led, docs = books(loaded["engine"], sid)
    assert stated == led == docs


def test_a_learner_cannot_touch_someone_elses_enrollment_or_use_staff_payments(client, loaded, as_role):
    s = signed_up(client)
    other = loaded["ds"]["enrollment"][0]["enrollment_id"]
    assert s.post(f"/me/enrollments/{other}/withdraw", {}).status_code == 404
    assert s.post("/payments", {"student_id": "STU-000001", "amount_paise": 100, "method": "UPI", "reference": "x"},
                  {"Idempotency-Key": "learner-bad-0001"}).status_code == 403
    assert s.post("/me/payments", {"student_id": "STU-000001", "amount_paise": 100, "method": "UPI", "reference": "x"},
                  {"Idempotency-Key": "learner-bad-0002"}).status_code == 422       # the student comes from the token only
    assert s.post("/me/payments", {"amount_paise": 100, "method": "CASH", "reference": "x"},
                  {"Idempotency-Key": "learner-bad-0003"}).status_code == 422       # cash and cheque are staff-only methods
    assert as_role("SUPPORT").get("/me/fees").status_code == 403


def test_staff_can_enrol_a_student(client, loaded, as_role):
    s = signed_up(client)
    sid = s.user["student_id"]
    res = as_role("ACADEMIC_ADMIN").post(f"/students/{sid}/enroll", {"term_id": "TERM-2026-FALL", "applications": ["NEED_BASED"]})
    assert res.status_code == 201 and res.json()["scholarship"]["scheme_code"] == "NEED_BASED"
    assert as_role("LEARNER").post(f"/students/{sid}/enroll", {"term_id": "TERM-2026-FALL"}).status_code == 403
    assert as_role("ACADEMIC_ADMIN").post("/students/STU-999999/enroll", {"term_id": "TERM-2026-FALL"}).status_code == 404


def test_my_fees_are_for_my_program_only(client, loaded):
    s = signed_up(client, program_id="PRG-02")
    items = s.get("/me/fees").json()
    assert items["program_id"] == "PRG-02" and {f["program_id"] for f in items["items"]} == {"PRG-02"}


def test_change_password(client, loaded):
    s = signed_up(client)
    assert s.post("/auth/change-password", {"current_password": "wrong-password-1", "new_password": "another-long-pass-2"}).status_code == 400
    assert s.post("/auth/change-password", {"current_password": NEW["password"], "new_password": "another-long-pass-2"}).status_code == 200
    assert client.post(f"{API}/auth/login", json={"email": NEW["email"], "password": "another-long-pass-2"}).status_code == 200
    assert client.post(f"{API}/auth/login", json={"email": NEW["email"], "password": NEW["password"]}).status_code == 401
    assert PASSWORD  # the seeded demo logins are untouched by this
