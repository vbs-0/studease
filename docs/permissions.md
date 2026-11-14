# Permission matrix

Generated from the route guards in `backend/app/api/` by `python -m app.cli docs`; do not edit by hand. A test fails when this file is stale, so it always matches the code.

| Method | Path | Learner | Instructor | Academic admin | Support | Platform admin | Scope and notes |
|---|---|---|---|---|---|---|---|
| GET | `/admin/users` | - | - | - | - | Yes |  |
| POST | `/admin/users` | - | - | - | - | Yes | Create a login for any role. A learner login must name an existing student; an instructor login names a program |
| POST | `/admin/users/{app_user_id}/enabled` | - | - | - | - | Yes |  |
| POST | `/auth/change-password` | Any | Any | Any | Any | Any |  |
| POST | `/auth/forgot` | Public | Public | Public | Public | Public | Always 202 with the same body. |
| POST | `/auth/login` | Public | Public | Public | Public | Public | Same answer for an unknown email and a wrong password. |
| GET | `/auth/me` | Any | Any | Any | Any | Any |  |
| GET | `/auth/programs` | Public | Public | Public | Public | Public | The program choices for the signup form (id, name and level only) |
| POST | `/auth/reset` | Public | Public | Public | Public | Public |  |
| POST | `/auth/signup` | Public | Public | Public | Public | Public | Creates a LEARNER only; the role and student id cannot be chosen. |
| GET | `/eligibility` | - | - | Yes | Yes | Yes |  |
| POST | `/enrollments/{enrollment_id}/withdraw` | - | - | Yes | - | Yes |  |
| GET | `/exceptions` | - | - | - | Yes | Yes |  |
| POST | `/exceptions/{exception_id}/resolve` | - | - | - | Yes | - | Support only: a platform admin can read the queue but resolution is a support duty. |
| GET | `/fee-schedules` | - | - | Yes | Yes | Yes |  |
| POST | `/fee-schedules` | - | - | Yes | - | Yes | Publish a new price version. The previous version of the same fee is closed the day before this one starts, so |
| GET | `/healthz` | Public | Public | Public | Public | Public |  |
| GET | `/invoices/{invoice_id}` | Yes | - | Yes | Yes | Yes | Learner: own invoices only (others answer 404). |
| POST | `/me/enroll` | Yes | - | - | - | - |  |
| GET | `/me/enrollable` | Yes | - | - | - | - |  |
| POST | `/me/enrollments/{enrollment_id}/withdraw` | Yes | - | - | - | - | Own enrollment only (others answer 404). |
| GET | `/me/fees` | Yes | - | - | - | - |  |
| POST | `/me/payments` | Yes | - | - | - | - | UPI, card or net banking only; the student comes from the token. |
| POST | `/me/profile` | Yes | - | - | - | - | Name and hostel flag only; GPA, income, residency and quota are staff-maintained. |
| GET | `/me/scholarships` | Yes | - | - | - | - |  |
| GET | `/metrics/overview` | - | - | Yes | Yes | Yes | Instructor: not allowed (it contains money). |
| POST | `/payments` | - | - | - | Yes | Yes | Any payment method; idempotent per caller. |
| GET | `/programs` | - | - | Yes | Yes | Yes |  |
| GET | `/quality` | - | - | - | - | Yes | The reports the generator and the evaluation wrote to reports/<scale>/ (committed with the repository) |
| GET | `/readyz` | Public | Public | Public | Public | Public |  |
| GET | `/scholarship-schemes` | - | - | Yes | Yes | Yes |  |
| GET | `/scholarships` | - | - | Yes | Yes | Yes |  |
| GET | `/scholarships/summary` | - | - | Yes | Yes | Yes |  |
| GET | `/students` | - | Yes | Yes | Yes | Yes | Instructor: own program only, no money columns. |
| POST | `/students` | - | - | Yes | Yes | Yes | Add a student (and, if an email and password are given, a learner login for them) |
| GET | `/students/{student_id}` | Any | Any | Any | Any | Any | Learner: own record only. Instructor: own program, enrolment status only (no balance or invoices). Others answer 404. |
| POST | `/students/{student_id}/enroll` | - | - | Yes | Yes | Yes |  |
| GET | `/students/{student_id}/events` | Yes | - | Yes | Yes | Yes | Learner: own only. Instructor: not allowed. |
| GET | `/students/{student_id}/ledger` | Yes | - | Yes | Yes | Yes | Learner: own only. Instructor: not allowed (no payment detail). |
| POST | `/students/{student_id}/profile` | - | - | Yes | Yes | Yes | All profile fields. |
| POST | `/students/{student_id}/scholarships` | - | - | Yes | - | Yes | Applies the scheme's criteria; staff cannot waive them. |
| GET | `/terms` | - | - | Yes | Yes | Yes |  |

## Reading the table

- **Yes** means the route's guard lists that role. **Any** means the route needs a signed-in user and then applies its own
  scope (see the notes column). **Public** means no sign-in.
- A disabled user is rejected on every request, whatever role an old token claims; the role is read from the database each time.
- A learner's student id always comes from the token, never from the URL or body.
- Out-of-scope objects answer **404**, the same as a missing one, so identifiers cannot be probed. A role that may never call a
  route gets **403**.

## What the app screens show

| Role | Navigation | Notable actions on screen |
|---|---|---|
| Learner | Account, Enrol, Scholarships, Fees | pay now, withdraw, enrol with scholarship checklist, export statement, change password, edit name and housing |
| Instructor | Students | read enrolment status of own program |
| Academic admin | Overview, Students, Fee schedules, Scholarships | new fee version, add student, edit profile, enrol, assign scholarship, withdraw |
| Support | Overview, Students, Fee schedules, Scholarships, Exceptions | record payment, add student, edit profile, enrol, resolve or dismiss exceptions |
| Platform admin | everything, plus Users and Data quality | everything above except resolving exceptions, plus create and disable users |

## What no role can do

- Edit or delete a posted ledger entry, event or allocation (the history is append-only; mistakes are corrected by new rows).
- Read the ground-truth table through the API (it is only read by the evaluation run).
- Waive scholarship criteria, or change another learner's password.
- Disable their own login.

