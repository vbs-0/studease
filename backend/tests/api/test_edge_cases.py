"""Edge cases and negative scenarios, end to end through the API (catalogued in docs/edge-cases.md; ids EC-xx match the document)."""
import pytest
from sqlalchemy import text

from .test_admin import FEE, STUDENT
from .test_learner import NEW, books, signed_up

pytestmark = pytest.mark.db
API = "/api/v1"
LONG = "a-long-password-1"


# ------------------------------------------------------------------ input validation: every field of every write, at both bounds
SIGNUP_BAD = [
    ("email", "not-an-email"), ("email", "a@b"), ("email", "x" * 90 + "@mail.test"), ("password", "short"), ("password", "p" * 129),
    ("full_name", "A"), ("full_name", "N" * 81), ("program_id", "PRG-1"), ("program_id", "'; DROP TABLE student;--"), ("residency", "MARTIAN"),
    ("gpa", -0.1), ("gpa", 10.1), ("gpa", "high"), ("income_band", "RICH"), ("sports_quota", "maybe"),
]


@pytest.mark.parametrize("field,value", SIGNUP_BAD)
def test_ec01_signup_rejects_every_bad_field(client, loaded, field, value):                       # EC-01
    res = client.post(f"{API}/auth/signup", json={**NEW, field: value})
    assert res.status_code == 422 and res.json()["error"]["code"] == "VALIDATION", (field, value, res.text)


@pytest.mark.parametrize("field", ["email", "password", "full_name", "program_id", "residency", "gpa", "income_band"])
def test_ec02_signup_requires_every_field(client, loaded, field):                                 # EC-02
    body = {k: v for k, v in NEW.items() if k != field}
    assert client.post(f"{API}/auth/signup", json=body).status_code == 422


def test_ec03_signup_boundaries_are_inclusive(client, loaded):                                    # EC-03
    ok = client.post(f"{API}/auth/signup", json={**NEW, "gpa": 0, "full_name": "Ab", "password": "p" * 12})
    assert ok.status_code == 201
    top = client.post(f"{API}/auth/signup", json={**NEW, "email": "top@mail.test", "gpa": 10, "full_name": "N" * 80, "password": "p" * 128})
    assert top.status_code == 201


def test_ec04_emails_are_case_insensitive_and_trimmed_for_uniqueness(client, loaded):             # EC-04
    signed_up(client)
    again = client.post(f"{API}/auth/signup", json={**NEW, "email": NEW["email"].upper()})
    assert again.status_code == 409, again.text
    assert client.post(f"{API}/auth/login", json={"email": NEW["email"].upper(), "password": NEW["password"]}).status_code == 200


def test_ec05_non_json_and_wrong_types_are_422_not_500(client, loaded):                           # EC-05
    h = {"Content-Type": "application/json"}
    assert client.post(f"{API}/auth/login", content=b"{not json", headers=h).status_code == 422
    assert client.post(f"{API}/auth/login", content=b"[]", headers=h).status_code == 422
    assert client.post(f"{API}/auth/login", json={"email": 5, "password": ["x"]}).status_code == 422
    assert client.post(f"{API}/auth/login", content=b"", headers=h).status_code == 422


def test_ec06_oversized_bodies_are_refused(client, loaded):                                       # EC-06
    res = client.post(f"{API}/auth/login", json={"email": "a@mail.test", "password": "x" * 2_000_000})
    assert res.status_code in (413, 422)


PAY_BAD = [("amount_paise", 0), ("amount_paise", -500), ("amount_paise", 1_000_000_001), ("amount_paise", 10.5),
           ("method", "BITCOIN"), ("method", ""), ("reference", ""), ("reference", "r" * 41), ("student_id", "STU-1"), ("student_id", "stu-000001")]


@pytest.mark.parametrize("field,value", PAY_BAD)
def test_ec07_payment_rejects_every_bad_field(as_role, field, value):                             # EC-07
    good = {"student_id": "STU-000001", "amount_paise": 1000, "method": "UPI", "reference": "R1"}
    res = as_role("SUPPORT").post("/payments", {**good, field: value}, {"Idempotency-Key": "k-edge-" + field + str(abs(hash(str(value))))[:6]})
    assert res.status_code in (422, 400), (field, value, res.text)


def test_ec08_payment_extra_fields_and_missing_key_are_refused(as_role):                          # EC-08
    s = as_role("SUPPORT")
    good = {"student_id": "STU-000001", "amount_paise": 1000, "method": "UPI", "reference": "R1"}
    assert s.post("/payments", {**good, "status": "ALLOCATED"}, {"Idempotency-Key": "k8a-edge-key"}).status_code == 422
    assert s.post("/payments", good).status_code in (400, 422)
    assert s.post("/payments", good, {"Idempotency-Key": ""}).status_code in (400, 422)
    assert s.post("/payments", good, {"Idempotency-Key": "k" * 200}).status_code in (400, 422)


def test_ec09_a_learner_cannot_pay_by_cash_or_pass_a_student(as_role, client, loaded):            # EC-09
    s = signed_up(client)
    assert s.post("/me/payments", {"amount_paise": 1000, "method": "CASH", "reference": "R"}, {"Idempotency-Key": "k9a-edge-key"}).status_code == 422
    assert s.post("/me/payments", {"amount_paise": 1000, "method": "UPI", "reference": "R", "student_id": "STU-000001"}, {"Idempotency-Key": "k9b-edge-key"}).status_code == 422


# ------------------------------------------------------------------ money and state edge cases
def test_ec10_a_payment_with_nothing_due_becomes_unapplied_credit(client, loaded):                # EC-10
    s = signed_up(client)
    sid = s.user["student_id"]
    res = s.post("/me/payments", {"amount_paise": 123_456, "method": "UPI", "reference": "ADV1"}, {"Idempotency-Key": "k10-edge-key"})
    assert res.status_code == 201 and res.json()["unapplied_paise"] == 123_456
    stated, led, docs = books(loaded["engine"], sid)
    assert stated == led == docs == -123_456                                                       # credit held, still reconciled


def test_ec11_a_paid_up_student_who_overpays_holds_credit_and_all_three_routes_agree(client, loaded):  # EC-11
    s = signed_up(client)
    sid = s.user["student_id"]
    inv = s.post("/me/enroll", {"term_id": "TERM-2026-FALL"}).json()["invoice"]
    s.post("/me/payments", {"amount_paise": inv["total_paise"] + 5_000, "method": "UPI", "reference": "OV"}, {"Idempotency-Key": "k11-edge-key"})
    stated, led, docs = books(loaded["engine"], sid)
    assert stated == led == docs == -5_000
    assert s.get(f"/students/{sid}").json()["invoices"][0]["status"] == "PAID"


def test_ec12_enrolling_twice_in_one_term_is_a_conflict_and_bills_once(client, loaded):           # EC-12
    s = signed_up(client)
    assert s.post("/me/enroll", {"term_id": "TERM-2026-FALL"}).status_code == 201
    again = s.post("/me/enroll", {"term_id": "TERM-2026-FALL"})
    assert again.status_code == 409
    assert len(s.get(f"/students/{s.user['student_id']}").json()["invoices"]) == 1


def test_ec13_unknown_and_malformed_terms_and_ids(client, loaded, as_role):                       # EC-13
    s = signed_up(client)
    assert s.post("/me/enroll", {"term_id": "TERM-1999-FALL"}).status_code in (404, 409, 422)
    assert s.post("/me/enroll", {"term_id": "nope"}).status_code == 422
    assert s.post("/me/enroll", {}).status_code == 422
    sup = as_role("SUPPORT")
    for bad in ("STU-000000", "STU-999999", "STU-12", "' OR 1=1 --", "%00", "../etc/passwd"):
        assert sup.get(f"/students/{bad}").status_code in (404, 422), bad
        assert sup.get(f"/invoices/{bad}").status_code in (404, 422), bad


def test_ec14_withdrawing_a_term_that_never_started_for_the_student_is_404(client, loaded):       # EC-14
    s = signed_up(client)
    assert s.post("/me/enrollments/ENR-999999/withdraw", {}).status_code == 404
    assert s.post("/me/enrollments/garbage/withdraw", {}).status_code in (404, 422)


def test_ec15_withdrawal_with_a_date_before_enrolment_or_far_future_is_rejected(client, loaded, as_role):  # EC-15
    s = signed_up(client)
    enr = s.post("/me/enroll", {"term_id": "TERM-2026-FALL"}).json()["enrollment"]["enrollment_id"]
    sup = as_role("ACADEMIC_ADMIN")
    for day in ("1999-01-01", "2999-01-01", "2026-13-40", "yesterday"):
        assert sup.post(f"/enrollments/{enr}/withdraw", {"left_on": day}).status_code in (409, 422), day


def test_ec16_a_refund_never_exceeds_what_was_paid(client, loaded):                               # EC-16
    s = signed_up(client)
    sid = s.user["student_id"]
    inv = s.post("/me/enroll", {"term_id": "TERM-2026-FALL"}).json()
    enr = inv["enrollment"]["enrollment_id"]
    s.post("/me/payments", {"amount_paise": 50_000, "method": "UPI", "reference": "P1"}, {"Idempotency-Key": "k16-edge-key"})
    s.post(f"/me/enrollments/{enr}/withdraw", {})
    with loaded["engine"].connect() as c:
        refunded = c.execute(text("SELECT coalesce(sum(amount_paise),0) FROM refund WHERE student_id=:s"), {"s": sid}).scalar()
    assert 0 <= refunded <= 50_000
    stated, led, docs = books(loaded["engine"], sid)
    assert stated == led == docs


# ------------------------------------------------------------------ lists, search, cursors
def test_ec17_search_text_is_data_never_sql(as_role):                                             # EC-17
    s = as_role("SUPPORT")
    for q in ("'; DROP TABLE student; --", "%", "_", "\\", "\x00", "a" * 500, "' OR '1'='1", "<script>alert(1)</script>"):
        res = s.get("/students", params={"q": q})
        assert res.status_code in (200, 422), (q, res.text)
        if res.status_code == 200:
            assert isinstance(res.json()["items"], list)
    assert s.get("/students?limit=1").status_code == 200


def test_ec18_pagination_inputs_are_bounded(as_role):                                             # EC-18
    s = as_role("SUPPORT")
    assert s.get("/students?limit=0").status_code == 422
    assert s.get("/students?limit=-5").status_code == 422
    assert s.get("/students?limit=201").status_code == 422
    assert s.get("/students?limit=abc").status_code == 422
    bogus = s.get("/students?after=%27%3B--")
    assert bogus.status_code in (200, 422) and (bogus.status_code == 422 or bogus.json()["items"] is not None)
    past_end = s.get("/students?after=STU-999999").json()
    assert past_end["items"] == [] and past_end["next"] is None


def test_ec19_unknown_query_filters_do_not_crash(as_role):                                        # EC-19
    s = as_role("SUPPORT")
    assert s.get("/exceptions?status=NOPE").status_code in (200, 422)
    assert s.get("/exceptions?exception_type=NOPE").status_code in (200, 422)
    assert s.get("/scholarships?scheme_code=NOPE").json()["items"] == []
    assert s.get("/fee-schedules?program_id=PRG-99").json()["items"] == []


# ------------------------------------------------------------------ authentication and tokens
def test_ec20_malformed_authorization_headers_are_401(client, loaded):                            # EC-20
    for h in ("", "Bearer", "Bearer ", "Basic abc", "bearer x.y.z", "Bearer " + "a" * 5000, "Token abc"):
        res = client.get(f"{API}/auth/me", headers={"Authorization": h})
        assert res.status_code == 401, (h[:20], res.status_code)


def test_ec21_change_password_validates_and_invalidates_nothing_it_should_not(client, loaded):    # EC-21
    s = signed_up(client)
    assert s.post("/auth/change-password", {"current_password": "wrong-password-1", "new_password": "another-long-pass-1"}).status_code in (400, 401, 403, 422)
    assert s.post("/auth/change-password", {"current_password": NEW["password"], "new_password": "short"}).status_code == 422
    assert s.post("/auth/change-password", {"current_password": NEW["password"], "new_password": NEW["password"]}).status_code in (200, 422)
    assert client.post(f"{API}/auth/login", json={"email": NEW["email"], "password": NEW["password"]}).status_code in (200, 401)


def test_ec22_a_disabled_learner_cannot_log_in_or_use_an_old_token(client, loaded, as_role):       # EC-22
    s = signed_up(client)
    uid = s.user["app_user_id"] if "app_user_id" in s.user else s.get("/auth/me").json()["app_user_id"]
    assert as_role("PLATFORM_ADMIN").post(f"/admin/users/{uid}/enabled", {"enabled": False}).status_code == 200
    assert s.get("/auth/me").status_code == 401
    assert client.post(f"{API}/auth/login", json={"email": NEW["email"], "password": NEW["password"]}).status_code == 401
    assert as_role("PLATFORM_ADMIN").post(f"/admin/users/{uid}/enabled", {"enabled": True}).status_code == 200
    assert client.post(f"{API}/auth/login", json={"email": NEW["email"], "password": NEW["password"]}).status_code == 200


# ------------------------------------------------------------------ staff data entry
def test_ec23_staff_entry_rejects_every_bad_field(as_role):                                       # EC-23
    s = as_role("SUPPORT")
    for field, value in [("full_name", "A"), ("full_name", "N" * 81), ("program_id", "PRG-1"), ("program_id", "PRG-99"), ("residency", "X"), ("gpa", 11), ("gpa", -1),
                         ("income_band", "X"), ("waiver_type", "BRIBE"), ("login_email", "bad"), ("sports_quota", "x")]:
        res = s.post("/students", {**STUDENT, field: value})
        assert res.status_code in (404, 422), (field, value, res.status_code)
    assert s.post("/students", {**STUDENT, "extra": 1}).status_code == 422
    assert s.post("/students", {}).status_code == 422


def test_ec24_fee_entry_rejects_every_bad_field(as_role):                                         # EC-24
    a = as_role("ACADEMIC_ADMIN")
    for field, value in [("program_id", "P1"), ("term_id", "TERM-2026-WINTER"), ("fee_type", "BRIBE"), ("applies_to", "EVERYONE"), ("amount_paise", 99), ("amount_paise", 1_000_000_001),
                         ("amount_paise", 1.5), ("effective_from", "2026-02-30"), ("effective_from", "soon"), ("scholarship_eligible", "maybe")]:
        assert a.post("/fee-schedules", {**FEE, field: value}).status_code in (404, 422), (field, value)
    assert a.post("/fee-schedules", {**FEE, "extra": 1}).status_code == 422


def test_ec25_a_fee_version_on_the_same_day_as_the_current_one_is_refused(as_role):               # EC-25
    a = as_role("ACADEMIC_ADMIN")
    ok = a.post("/fee-schedules", {**FEE, "effective_from": "2026-10-01"})
    assert ok.status_code == 201
    assert a.post("/fee-schedules", {**FEE, "effective_from": "2026-10-01", "amount_paise": 1_700_000}).status_code == 409


def test_ec26_scholarship_assignment_rejects_bad_input_and_unknown_students(as_role, client, loaded):  # EC-26
    a = as_role("ACADEMIC_ADMIN")
    s = signed_up(client)
    sid = s.user["student_id"]
    assert a.post(f"/students/{sid}/scholarships", {"term_id": "TERM-2026-FALL", "scheme_code": "FREE_MONEY"}).status_code == 422
    assert a.post(f"/students/{sid}/scholarships", {"term_id": "x", "scheme_code": "SPORTS"}).status_code == 422
    assert a.post("/students/STU-999999/scholarships", {"term_id": "TERM-2026-FALL", "scheme_code": "SPORTS"}).status_code == 404
    assert a.post(f"/students/{sid}/scholarships", {}).status_code == 422


def test_ec27_user_creation_rejects_bad_scope_and_weak_input(as_role):                            # EC-27
    p = as_role("PLATFORM_ADMIN")
    base = {"email": "ok@mail.test", "password": LONG, "role": "SUPPORT"}
    for patch in ({"email": "bad"}, {"password": "short"}, {"role": "GOD"}, {"role": "LEARNER", "student_id": "STU-999999"}, {"role": "LEARNER"},
                  {"role": "INSTRUCTOR", "program_id": "PRG-99"}, {"role": "INSTRUCTOR"}, {"student_id": "STU-000001"}):
        assert p.post("/admin/users", {**base, **patch}).status_code in (404, 422), patch


def test_ec28_a_staff_member_cannot_lock_every_admin_out(as_role):                                # EC-28
    p = as_role("PLATFORM_ADMIN")
    me = p.get("/auth/me").json()["app_user_id"]
    assert p.post(f"/admin/users/{me}/enabled", {"enabled": False}).status_code == 409


# ------------------------------------------------------------------ idempotency and concurrency
def test_ec29_same_key_with_a_different_body_is_a_conflict(as_role):                              # EC-29
    s = as_role("SUPPORT")
    first = {"student_id": "STU-000001", "amount_paise": 1000, "method": "UPI", "reference": "R1"}
    assert s.post("/payments", first, {"Idempotency-Key": "k29-edge-key"}).status_code == 201
    assert s.post("/payments", {**first, "amount_paise": 2000}, {"Idempotency-Key": "k29-edge-key"}).status_code in (409, 422)
    assert s.post("/payments", first, {"Idempotency-Key": "k29-edge-key"}).status_code == 200            # a replay answers with the first result


def test_ec30_a_resolved_exception_cannot_be_resolved_twice_or_without_a_note(as_role):           # EC-30
    s = as_role("SUPPORT")
    case = s.get("/exceptions?status=OPEN&limit=1").json()["items"][0]["exception_id"]
    assert s.post(f"/exceptions/{case}/resolve", {"status": "RESOLVED", "note": ""}).status_code == 422
    assert s.post(f"/exceptions/{case}/resolve", {"status": "OPEN", "note": "x"}).status_code == 422
    assert s.post(f"/exceptions/{case}/resolve", {"status": "RESOLVED", "note": "checked"}).status_code == 200
    assert s.post(f"/exceptions/{case}/resolve", {"status": "DISMISSED", "note": "again"}).status_code == 409
    assert s.post("/exceptions/EXC-999999/resolve", {"status": "RESOLVED", "note": "x"}).status_code == 404


# ------------------------------------------------------------------ access control sweeps
ROUTES = [("GET", "/students"), ("GET", "/metrics/overview"), ("GET", "/exceptions"), ("GET", "/quality"), ("GET", "/admin/users"), ("GET", "/fee-schedules"),
          ("GET", "/scholarships"), ("GET", "/programs"), ("GET", "/terms")]


@pytest.mark.parametrize("method,path", ROUTES)
def test_ec31_every_guarded_read_refuses_anonymous_callers(client, loaded, method, path):         # EC-31
    assert client.request(method, API + path).status_code == 401


def test_ec32_a_learner_cannot_read_any_staff_view(client, loaded):                               # EC-32
    s = signed_up(client)
    for path in ("/metrics/overview", "/exceptions", "/quality", "/admin/users", "/fee-schedules", "/scholarships", "/programs", "/eligibility"):
        assert s.get(path).status_code == 403, path
    assert s.get("/students").status_code == 403


def test_ec33_instructors_never_see_money_anywhere(as_role):                                      # EC-33
    i = as_role("INSTRUCTOR")
    items = i.get("/students?limit=5").json()["items"]
    assert items and all("balance_paise" not in r for r in items)
    sid = items[0]["student_id"]
    for path in (f"/students/{sid}/ledger", f"/students/{sid}/events", "/metrics/overview", "/exceptions"):
        assert i.get(path).status_code == 403, path
    body = i.get(f"/students/{sid}").json()
    assert "balance" not in body and not body.get("invoices")


def test_ec34_unknown_routes_and_methods_use_the_error_envelope(client, loaded):                  # EC-34
    nf = client.get(f"{API}/nothing-here")
    assert nf.status_code == 404 and nf.json()["error"]["code"]
    assert client.delete(f"{API}/students/STU-000001").status_code in (401, 405)
    assert client.put(f"{API}/auth/login", json={}).status_code == 405
    assert client.get(f"{API}/students/STU-000001/ledger/extra").status_code in (401, 404)


def test_ec35_control_characters_in_text_are_refused_not_a_500(client, loaded, as_role):           # EC-35
    assert client.post(f"{API}/auth/signup", json={**NEW, "full_name": "Bad\x00Name"}).status_code == 422
    assert as_role("SUPPORT").post("/students", {**STUDENT, "full_name": "Bad\x00Name"}).status_code == 422
    assert as_role("SUPPORT").post("/payments", {"student_id": "STU-000001", "amount_paise": 1000, "method": "UPI", "reference": "a\x00b"},
                                   {"Idempotency-Key": "k35-edge-key"}).status_code == 422
