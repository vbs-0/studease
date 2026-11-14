# Edge cases and negative scenarios

Every row says what the caller does, what the system must answer, what enforces it, and the test that proves it. The **EC-xx** tests live in
[`backend/tests/api/test_edge_cases.py`](../backend/tests/api/test_edge_cases.py); the rest are older tests named in the last column. A row is
only here if a test fails when the behaviour breaks. Gaps we chose to leave are listed honestly at the end.

Conventions: **422** = the request is invalid (error code `VALIDATION`, or a named business code), **409** = valid but conflicts with current
state, **404** = missing or out of your scope (the two look the same on purpose), **403** = role never allowed, **401** = no or bad credentials.
Every error is the same envelope: `{"error": {"code", "message", "request_id"}}`.

## 1. Input validation (all write endpoints)

| ID | Scenario | Expected | Enforced by | Test |
|---|---|---|---|---|
| EC-01 | Sign-up with a bad email, short or long password, 1-char or 81-char name, malformed program id, SQL text as program id, unknown residency, GPA below 0 or above 10 or non-numeric, unknown income band, non-boolean flag | 422 `VALIDATION`, nothing stored | pydantic request model (`extra="forbid"`, patterns, ranges) | `test_ec01` (15 cases) |
| EC-02 | Sign-up with any required field missing | 422 | request model | `test_ec02` (7 cases) |
| EC-03 | Boundary values: GPA 0 and 10, 2-char and 80-char name, 12 and 128-char password | accepted (bounds are inclusive) | request model | `test_ec03` |
| EC-04 | Same email in a different case | 409 on sign-up, login works in any case | `lower(email)` on every lookup | `test_ec04` |
| EC-05 | Body is not JSON, is `[]`, is empty, or has wrong types | 422, never 500 | FastAPI body parsing + handler | `test_ec05` |
| EC-06 | A 2 MB password | refused (413 or 422), the server does not hash it | field `max_length` and body limit | `test_ec06` |
| EC-07 | Payment with amount 0, negative, above Rs 1 crore, fractional, unknown method, empty or 41-char reference, malformed student id | 422 | `NewPayment` model | `test_ec07` (10 cases) |
| EC-08 | Payment with an extra field (for example `status`), no `Idempotency-Key`, an empty key, a 200-char key | 422 | `extra="forbid"`; key must be 8-80 of `A-Za-z0-9-_:.` | `test_ec08` |
| EC-09 | A learner pays cash or names another student | 422 (their own model allows only UPI, card, net banking and no student id) | `OwnPayment` model | `test_ec09` |
| EC-23 | Staff add student with any bad field, an extra field, or an empty body | 422 (or 404 for an unknown program) | `NewStudent` model | `test_ec23` (11 cases) |
| EC-24 | Fee version with a bad program, term, fee type, audience, amount below Re 1 or above Rs 1 crore, fractional amount, impossible date (30 Feb), non-boolean flag | 422 or 404 | `NewFee` model | `test_ec24` (10 cases) |
| EC-26 | Assign scholarship with an unknown scheme, malformed term, unknown student, empty body | 422 / 404 | `AssignAward` model | `test_ec26` |
| EC-27 | Create user with a bad email, short password, unknown role, learner without or with an unknown student id, instructor without or with an unknown program, staff role carrying a student id | 422 / 404 | `NewUser` model + role-scope check | `test_ec27` |
| EC-35 | A NUL or other control character inside any text field | 422, not a 500 | error handler maps the database refusal to `VALIDATION`; student search forbids control characters by pattern | `test_ec35`, `test_ec17` |

The browser forms repeat the same rules (required, pattern, min and max length, `type="email"`, `type="date"`) so most mistakes are caught before
a request is sent; the server is still the authority, and every row above is tested against the server.

## 2. Money and state

| ID | Scenario | Expected | Enforced by | Test |
|---|---|---|---|---|
| EC-10 | A learner pays before anything is billed | 201; the whole amount is **unapplied credit**; balance is negative and the three balance routes agree | allocation leaves the remainder as credit | `test_ec10` |
| EC-11 | Overpaying a bill | invoice becomes PAID, the surplus is held as credit, books reconcile | allocation + ledger | `test_ec11` |
| EC-12 | Enrolling twice in the same term | 409; exactly one invoice | unique `(student, term)` + service check | `test_ec12` |
| EC-13 | Unknown or malformed term ids; hostile ids (`' OR 1=1 --`, `../etc/passwd`, `%00`) in URL paths | 404 / 422 | path patterns, parameterised SQL | `test_ec13` |
| EC-14 | Withdrawing an enrollment that does not exist or is not yours | 404 | scope check | `test_ec14`, `test_a_learner_cannot_touch_someone_elses_enrollment_or_use_staff_payments` |
| EC-15 | Withdrawal date before enrolment, far in the future, impossible, or not a date | 409 / 422 | `Withdraw` model + date rules | `test_ec15`, `test_withdrawing_twice_is_a_conflict_and_a_bad_date_is_rejected` |
| EC-16 | Withdrawing after paying | refund never exceeds what was paid; books reconcile | refund cap (R-REF-1) | `test_ec16` |
| EC-29 | The same idempotency key with the same body | replays the first result (200), nothing written twice | idempotency table (user + key + body hash) | `test_ec29`, `test_s9_*` |
| EC-29 | The same key with a **different** body | 422 `IDEMPOTENCY_MISMATCH` | body hash comparison | `test_ec29` |
| EC-30 | Resolving an exception without a note, with status OPEN, twice, or one that does not exist | 422 / 409 / 404 | `Resolve` model + state check | `test_ec30`, `test_resolving_an_exception_closes_it_once_and_writes_an_event` |
| EC-25 | New fee version on the same date as the current one | 409 (versions must move forward) | version check | `test_ec25`, `test_fee_versions_must_move_forward_and_keep_their_audience` |
| existing | Two payments at the same instant for one student | no double allocation | student row lock | `test_s15_concurrent_payments_for_one_student_never_double_allocate` |
| existing | Payment larger than the debt | remainder kept as credit | allocation | `test_a_payment_larger_than_the_debt_keeps_the_rest_as_credit` |
| existing | Cancel before the term starts | full refund, award revoked | withdrawal rules | `test_cancelling_before_the_term_starts_refunds_in_full_and_revokes_the_award` |
| existing | Enrol into a term that has ended | refused | enrolment rules | `test_enrolling_into_an_ended_term_is_refused` |
| existing | Scholarship above the eligible fees, ties between schemes, sports-quota and international rules | capped; lowest priority number wins | `domain/` scholarship rules | `tests/domain/*` |
| existing | Credits, waivers, rounding (half up), basis points | integer paise throughout | `domain/billing.py`, `money.py` | `tests/domain/*`, `test_ids_money.py` |
| existing | Assigning an award the student does not qualify for | 422 `NOT_ELIGIBLE`; a second award 409 `ALREADY_AWARDED`; no enrolment 409 `NOT_ENROLLED` | `assign_scholarship` | `test_assigning_*` in `test_admin.py` |

## 3. Lists, search and cursors

| ID | Scenario | Expected | Enforced by | Test |
|---|---|---|---|---|
| EC-17 | Search for `'; DROP TABLE student; --`, `%`, `_`, backslash, NUL, 500 characters, `<script>` | harmless: empty or matching results, or 422; never an error page | bound parameters; `max_length=40`; control-character pattern | `test_ec17`, `test_s1_no_sql_is_built_from_strings` |
| EC-18 | `limit` of 0, negative, 201, or text; a junk or past-the-end cursor | 422 for limits; empty page and no `next` past the end | `Page` model (1..200) | `test_ec18` |
| EC-19 | Unknown filter values | empty list or 422, never 500 | parameterised filters | `test_ec19` |
| existing | Paging without gaps or repeats | keyset on the id | `Page` | `test_students_list_pages_by_keyset_without_gaps_or_repeats` |

## 4. Authentication, tokens and accounts

| ID | Scenario | Expected | Enforced by | Test |
|---|---|---|---|---|
| EC-20 | `Authorization` header empty, `Bearer` alone, `Basic`, lowercase, 5,000 characters | 401 | token parser | `test_ec20` |
| EC-21 | Change password: wrong current, too short new, same as current | refused or accepted without breaking login | `ChangePassword` model | `test_ec21` |
| EC-22 | A disabled learner with a valid token, or trying to log in; then re-enabled | 401 until re-enabled | role and `enabled` read from the database each request | `test_ec22`, `test_s7_a_disabled_user_is_rejected_at_once` |
| EC-28 | An admin disables their own account | 409 (cannot lock yourself out) | `set_enabled` | `test_ec28`, `test_admin_user_management` |
| existing | Token with the wrong key or algorithm, an expired token, a reset token used as an access token | 401 | JWT HS256 pinned, token type claim | `test_s7_*`, `test_a_reset_token_cannot_be_used_as_an_access_token` |
| existing | Unknown email versus wrong password | identical answer | single code path | `test_s4_unknown_email_and_wrong_password_look_identical` |
| existing | Forgot-password for known and unknown emails; a reset link used twice | same 202; link works once and only for its user | one-time token | `test_s23_*` |
| existing | Sign-up trying to set a role or student id | refused | model has no such fields | `test_signup_cannot_choose_a_role_or_a_student` |
| existing | A malformed stored password hash | login fails cleanly | verify wrapper | `test_a_malformed_stored_hash_is_a_failure_not_a_crash` |

## 5. Access control

| ID | Scenario | Expected | Enforced by | Test |
|---|---|---|---|---|
| EC-31 | Any guarded read without a token | 401 | `current_user` | `test_ec31` (9 routes) |
| EC-32 | A learner calls any staff view | 403 | `require_role` | `test_ec32` |
| EC-33 | An instructor asks for money, ledger, events, overview or exceptions | 403; list rows carry no balance; detail carries no balance or invoices | role guard + field projection | `test_ec33` |
| EC-34 | Unknown route, `DELETE`, `PUT`, extra path segment | envelope with 404 / 405, never a stack trace | handlers | `test_ec34`, `test_s12_*` |
| existing | A learner reads another learner's student, ledger or invoice | 404 | object-level scope | `test_a_learner_sees_only_their_own_account` |
| existing | Every write by the wrong role | 403 | role guard | `test_writes_are_limited_to_their_roles` |
| existing | Allowed roles per route, always current | generated | route introspection | [`permissions.md`](permissions.md), `test_docs.py` |
| existing | Unknown JSON fields and bad values on writes | 422 | `extra="forbid"` | `test_s10_unknown_fields_and_bad_values_are_rejected` |
| existing | CORS from an origin that is not configured | no CORS headers | middleware | `test_s11_cors_allows_only_configured_origins` |
| existing | Production started with default secrets | refuses to start | settings check | `test_s6_production_refuses_default_secrets` |

## 6. Data and reconciliation (the hackathon core)

| Scenario | Expected | Where |
|---|---|---|
| Payment allocated beyond its amount | exception `ALLOC_EXCEEDS_PAYMENT` | detectors, `tests/engine/*` |
| Scholarship above eligible fees | `SCHOLARSHIP_EXCEEDS_ELIGIBLE` | detectors |
| Duplicate invoice for one enrollment and term | `DUPLICATE_INVOICE` | detectors |
| Refund above net paid | `REFUND_EXCEEDS_NET_PAID` | detectors |
| Stated balance differs from the ledger | `BALANCE_LEDGER_MISMATCH` | detectors |
| Generated data breaks a rule (negative money, dangling id, bad status transition) | the validator fails the load | `engine/validate.py`, `tests/engine/*` |
| Generating the same seed twice | identical data, deterministic | `tests/datagen/*` |

## 7. Gaps left on purpose

- **No rate limiting on login.** Deferred by decision (see `decisions.md`); `test_throttling_is_deliberately_absent_for_now` pins it so adding it is a
  conscious change. The production fix is nginx `limit_req` on `/api/v1/auth/`.
- **Passwords are not checked against breach lists**, only length (12 to 128).
- **Reset and receipt emails need working SMTP.** Without it the app logs a line and still answers 202.
- **A retroactive price change** must be entered as a new version dated on or after the current one; dates before it are refused, which is the safe default.
- **Payment gateways are simulated.** "UPI", "card" and "net banking" record a payment; no money moves.
