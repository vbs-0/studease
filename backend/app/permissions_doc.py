"""docs/permissions.md: the permission matrix, generated from the route guards themselves.

Each route is read from the FastAPI app: a `require_role(...)` dependency gives the roles, a route that only needs a
signed-in user is open to every role, and a route with neither is public. Because the table is read from the code, it cannot
disagree with it, and a test fails if the committed copy is stale."""
from __future__ import annotations

ROLES = ["LEARNER", "INSTRUCTOR", "ACADEMIC_ADMIN", "SUPPORT", "PLATFORM_ADMIN"]
SHORT = {"LEARNER": "Learner", "INSTRUCTOR": "Instructor", "ACADEMIC_ADMIN": "Academic admin", "SUPPORT": "Support", "PLATFORM_ADMIN": "Platform admin"}

# Rules that the role list alone does not say (object-level scope, money hidden, etc.), keyed by "METHOD path".
SCOPE = {
    "GET /api/v1/students": "Instructor: own program only, no money columns.",
    "GET /api/v1/students/{student_id}": "Learner: own record only. Instructor: own program, enrolment status only (no balance or invoices). Others answer 404.",
    "GET /api/v1/students/{student_id}/ledger": "Learner: own only. Instructor: not allowed (no payment detail).",
    "GET /api/v1/students/{student_id}/events": "Learner: own only. Instructor: not allowed.",
    "GET /api/v1/invoices/{invoice_id}": "Learner: own invoices only (others answer 404).",
    "POST /api/v1/payments": "Any payment method; idempotent per caller.",
    "POST /api/v1/me/payments": "UPI, card or net banking only; the student comes from the token.",
    "POST /api/v1/me/enrollments/{enrollment_id}/withdraw": "Own enrollment only (others answer 404).",
    "POST /api/v1/students/{student_id}/profile": "All profile fields.",
    "POST /api/v1/me/profile": "Name and hostel flag only; GPA, income, residency and quota are staff-maintained.",
    "POST /api/v1/students/{student_id}/scholarships": "Applies the scheme's criteria; staff cannot waive them.",
    "POST /api/v1/auth/signup": "Creates a LEARNER only; the role and student id cannot be chosen.",
    "POST /api/v1/auth/login": "Same answer for an unknown email and a wrong password.",
    "POST /api/v1/auth/forgot": "Always 202 with the same body.",
    "GET /api/v1/metrics/overview": "Instructor: not allowed (it contains money).",
    "POST /api/v1/exceptions/{exception_id}/resolve": "Support only: a platform admin can read the queue but resolution is a support duty.",
}

PROSE = """
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
"""


def _roles_of(route) -> tuple[list[str] | None, bool]:
    """(roles from a require_role guard or None, whether the route needs a signed-in user)."""
    for dep in route.dependencies:
        roles = getattr(dep.dependency, "roles", None)
        if roles:
            return list(roles), True

    def walk(dependant) -> bool:
        return any(getattr(d.call, "__name__", "") == "current_user" or walk(d) for d in dependant.dependencies)
    return None, walk(route.dependant)


def _routes(app):
    """Every API route with its final path and guards. Included routers are flattened through FastAPI's effective contexts."""
    for r in app.routes:
        if hasattr(r, "effective_route_contexts"):
            yield from r.effective_route_contexts()
        elif hasattr(r, "dependant"):
            yield r


def permissions_md() -> str:
    from app.main import app
    rows = []
    for route in _routes(app):
        if not route.path.startswith("/api/v1") or not route.include_in_schema:
            continue
        roles, signed_in = _roles_of(route)
        for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
            if roles is not None:
                cells = ["Yes" if r in roles else "-" for r in ROLES]
            elif signed_in:
                cells = ["Any"] * len(ROLES)
            else:
                cells = ["Public"] * len(ROLES)
            doc = (route.endpoint.__doc__ or "").strip().split("\n")[0].rstrip(".")
            key = f"{method} {route.path}"
            note = " ".join(x for x in (SCOPE.get(key, ""), doc if not SCOPE.get(key) else "") if x)
            rows.append((route.path, method, cells, note))
    rows.sort(key=lambda r: (r[0], r[1]))
    out = ["# Permission matrix\n",
           "Generated from the route guards in `backend/app/api/` by `python -m app.cli docs`; do not edit by hand. "
           "A test fails when this file is stale, so it always matches the code.\n",
           "| Method | Path | " + " | ".join(SHORT[r] for r in ROLES) + " | Scope and notes |",
           "|---|---|" + "---|" * len(ROLES) + "---|"]
    for path, method, cells, note in rows:
        out.append(f"| {method} | `{path.removeprefix('/api/v1')}` | " + " | ".join(cells) + f" | {note} |")
    out.append(PROSE)
    return "\n".join(out) + "\n"
