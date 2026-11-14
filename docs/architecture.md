# StudEase: architecture and business rules

StudEase calculates tuition and fees, applies scholarship eligibility and payments, and reconciles student
balances. This document is the specification: every rule the code enforces is stated here once, with the
number that the code uses. If code and this document disagree, that is a bug.

Date fixed for the dataset ("as of"): **2026-10-22**. Seed: **20261022**. Currency: **INR, stored as integer
paise** (`*_paise` columns, 1 INR = 100 paise). No floats anywhere in money paths.

## 1. Three tiers

```
frontend/   Presentation   React 19 + Vite + TypeScript + Tailwind v4. Static build served by nginx.
backend/    Application    FastAPI + SQLAlchemy Core. Domain rules, data generator, validation,
                           detection, evaluation, REST API under /api/v1.
database/   Data           PostgreSQL 14+. Alembic migrations, generated schema.sql, seed SQL.
```

Rules for the boundaries:

- The frontend talks only to `/api/v1` over HTTP. It holds no business rules; it formats and displays.
- The backend is the only thing that connects to Postgres.
- The database enforces what it can on its own: primary keys, foreign keys, `CHECK` on enums, amounts and
  date order, unique constraints. A row the rules forbid should be rejected even if the backend has a bug.
- `backend/app/domain/` is pure Python (no database, no HTTP, no clock, no randomness). The generator, the
  API and the detectors all call the same functions, so a rule exists in exactly one place.

```
                +------------------- backend ---------------------+
 browser ---->  | api/  --->  domain/  <---  datagen/  engine/    |  ---> PostgreSQL
 (frontend)     |  (HTTP)    (pure rules)   (simulate) (detect)   |      (database/)
                +--------------------------------------------------+
                         cli.py: generate | validate | load | reconcile | export | repro | all
```

## 2. Repository layout

```
CandidateWorkspace/
  README.md  Makefile  LICENSE  .gitignore
  .github/workflows/ci.yml        lint, tests, generate starter, validate, repro check
  backend/
    pyproject.toml  uv.lock  .env.example
    app/
      main.py        FastAPI app factory, middleware, /healthz, /readyz
      config.py      settings from environment
      db.py          engine, connection dependency
      schema.py      every table, with data-dictionary metadata on each column (single source of truth)
      ids.py         ID formats and validators
      money.py       paise helpers: percent, format
      security.py    password hashing (scrypt), JWT, reset tokens
      mail.py        SMTP sender (skipped when not configured)
      logging.py     JSON logs, request id
      cli.py         command line entry
      domain/        calendar.py fees.py billing.py scholarships.py allocation.py latefees.py
                     withdrawal.py ledger.py status.py
      datagen/       rand.py catalog.py people.py simulate.py anomalies.py generator.py writer.py
                     validate.py repro.py
      engine/        detect.py evaluate.py pipeline.py loader.py
      api/           deps.py errors.py auth.py students.py invoices.py fees.py scholarships.py
                     payments.py exceptions.py metrics.py ops.py
    tests/           domain/ datagen/ engine/ api/  (mirrors app/)
  frontend/
    package.json  vite.config.ts  index.html
    src/  main.tsx App.tsx index.css
          lib/        api.ts auth.tsx format.ts motion.ts types.ts (generated from OpenAPI)
          components/ Shell.tsx ui.tsx charts.tsx
          pages/      Login Overview Students StudentLedger Invoice FeeSchedules Scholarships
                      Exceptions DataQuality MyAccount
  database/
    alembic.ini  migrations/env.py  migrations/versions/0001_initial.py
    schema.sql          generated DDL (reviewable without running anything)
    seed/               starter seed SQL (generated)
    README.md
  data/
    starter/  *.csv *.json manifest.json   ground_truth/ground_truth.csv and .json
    full/     *.csv.gz manifest.json       ground_truth/ground_truth.csv.gz
  reports/    starter and full: validation_summary.json evaluation.json repro.json
  docs/       architecture.md (this) practices.md decisions.md walkthrough.md testing.md deploy.md
              data_dictionary.md (generated) erd.md (generated) plans/
  scripts/    scrub_check.py (fails if private details are about to be published)
  deploy/     deploy.sh nginx-studease.conf studease-api.service
  prompts/    prompt history (required by the submission guidelines)
```

## 3. Actors and what each can do

| Role (code) | Actor in the brief | Can see | Can do |
|---|---|---|---|
| `LEARNER` | Learner | own account only | read own ledger, invoices, awards |
| `INSTRUCTOR` | Instructor | students of own program: enrollment and hold status, no payment detail | read |
| `ACADEMIC_ADMIN` | Academic administrator | fee schedules, programs, enrollments, scholarships | read; withdraw an enrollment |
| `SUPPORT` | Support staff | all student accounts, exceptions queue | record a payment, resolve or dismiss an exception |
| `PLATFORM_ADMIN` | Platform administrator | everything plus data quality | everything above |

Authentication: email + password, JWT (HS256, 8 h). Demo logins are seeded, one per role; the password
comes from the `DEMO_PASSWORD` environment variable and is never committed. Every write is authorised by
role in one dependency (`require_role`), and a learner's student id comes from the token, never from the
URL. The full security design is in section 12.

## 4. Entities

Master data first, then dependents. All ids are immutable strings.

| Entity (table) | Primary key, format | Parents (FK) | Notes |
|---|---|---|---|
| Program (`program`) | `program_id` `PRG-01` | | 20 programs, level UG / PG / DIPLOMA |
| Term (`term`) | `term_id` `TERM-2026-FALL` | | 3 terms in 2026; holds the dates rules need |
| Student (`student`) | `student_id` `STU-000001` | program | attributes that scholarship rules read |
| FeeSchedule (`fee_schedule`) | `fee_schedule_id` `FEE-PRG-01-2026-FALL-TUITION-V1` | program, term | effective-dated price of one fee type |
| ScholarshipScheme (`scholarship_scheme`) | `scheme_code` `MERIT_GOLD` | | the criteria and the award formula |
| Enrollment (`enrollment`) | `enrollment_id` `ENR-000001-2026-FALL` | student, program, term | unique (student, term) |
| Invoice (`invoice`) | `invoice_id` `INV-STU-000001-2026-000001` | student, enrollment, term | counter is global, zero padded |
| InvoiceLine (`invoice_line`) | `invoice_line_id` `<invoice_id>-L01` | invoice, fee_schedule?, scholarship?, applies_to_line? | charges are positive, credits negative |
| Eligibility (`eligibility`) | `eligibility_id` `ELG-2026-000001` | student, term, scheme | one decision per application, with reason |
| Scholarship (`scholarship`) | `scholarship_id` `SCH-2026-000001` | eligibility (1:1), student, term, scheme, invoice | the award |
| Payment (`payment`) | `payment_id` `PAY-2026-000001` | student | money received |
| PaymentAllocation (`payment_allocation`) | `allocation_id` `ALLOC-PAY-2026-000001-01` | payment, invoice_line | bridge: Payment N:M InvoiceLine |
| Refund (`refund`) | `refund_id` `REF-2026-000001` | student, invoice?, payment? | money returned |
| LedgerEntry (`ledger_entry`) | `entry_id` `LED-0000001` | student | append-only; the balance is its sum |
| StudentBalance (`student_balance`) | `student_id` | student (1:1) | the stated balance, checked against the ledger |
| Event (`event`) | `event_id` `EVT-0000001` | (entity_type, entity_id) | append-only state history |
| Exception (`exception`) | `exception_id` `EXC-000001` | student | detector output, worked by support staff |
| GroundTruth (`gt.ground_truth`) | `gt_id` `GT-000001` | | separate schema and separate folder; never joined into inputs |
| AppUser (`app_user`) | `app_user_id` | student?, program? | logins and roles |
| IdempotencyKey (`idempotency_key`) | (`app_user_id`, `key`) | app_user | replay protection for writes (S-9) |

Cardinality:

- Program 1:N Student, Program 1:N FeeSchedule, Term 1:N FeeSchedule, Program 1:N Enrollment
- Student 1:N Enrollment, Term 1:N Enrollment; Enrollment 1:N Invoice (normally 1; 2 only for the labelled
  duplicate anomaly)
- Invoice 1:N InvoiceLine; FeeSchedule 1:N InvoiceLine (optional on the line: late fees and adjustments
  have no fee schedule)
- InvoiceLine 1:N InvoiceLine through `applies_to_line_id` (a credit points at the charge it reduces)
- Student 1:N Eligibility; Eligibility 1:0..1 Scholarship; Scholarship 1:N InvoiceLine (its credit lines)
- Student 1:N Payment; Payment N:M InvoiceLine through PaymentAllocation
- Student 1:N Refund; Refund N:1 Invoice (optional), N:1 Payment (optional)
- Student 1:N LedgerEntry; Student 1:1 StudentBalance

Lifecycle states. Every transition writes an `event` row. Nothing is updated in place except the current
`status` column, whose history is in `event`.

| Entity | States | Allowed transitions |
|---|---|---|
| Enrollment | ENROLLED, COMPLETED, WITHDRAWN, CANCELLED | ENROLLED to COMPLETED, WITHDRAWN or CANCELLED |
| Invoice | ISSUED, PARTIALLY_PAID, PAID, OVERDUE, CANCELLED, VOID | ISSUED to PARTIALLY_PAID to PAID; ISSUED or PARTIALLY_PAID to OVERDUE to PAID; any open state to CANCELLED; ISSUED to VOID |
| Eligibility | ELIGIBLE, INELIGIBLE | terminal on creation |
| Scholarship | AWARDED, APPLIED, REVOKED | AWARDED to APPLIED to REVOKED |
| Payment | RECEIVED, PARTIALLY_ALLOCATED, ALLOCATED | RECEIVED to PARTIALLY_ALLOCATED to ALLOCATED |
| Refund | APPROVED, PAID | APPROVED to PAID |
| Exception | OPEN, RESOLVED, DISMISSED | OPEN to RESOLVED or DISMISSED |

## 5. Business rules

### 5.1 Terms

| Term | Starts | Ends | Invoice issued | Due |
|---|---|---|---|---|
| TERM-2026-SPRING | 2026-01-12 | 2026-05-08 | 2026-01-05 | 2026-02-04 |
| TERM-2026-SUMMER | 2026-05-25 | 2026-07-31 | 2026-05-18 | 2026-06-17 |
| TERM-2026-FALL | 2026-08-17 | 2026-12-11 | 2026-08-10 | 2026-09-09 |

Due date is always issue date + 30 days.

### 5.2 Fee schedules (R-FEE)

A fee schedule row prices one fee type for one program and term, for an audience, between two dates.

| Fee type | Who is charged (`applies_to`) | Scholarship eligible | Notes |
|---|---|---|---|
| TUITION | ALL | yes | base by program level; SUMMER is 40% of the regular-term amount |
| LAB | ALL, only on programs with `has_lab` | yes | |
| LIBRARY | ALL | no | |
| TECHNOLOGY | ALL | no | |
| EXAM | ALL | no | |
| INTL_SURCHARGE | INTERNATIONAL | no | |
| HOSTEL | HOSTEL (students with `hostel_resident`); not offered in SUMMER | no | |

- R-FEE-1: a line is generated for a fee schedule row only if the student is in its audience and the row
  is effective on the invoice issue date (`effective_from <= issue_date` and (`effective_to` is null or
  `issue_date <= effective_to`)).
- R-FEE-2: for one program, term, fee type and audience, effective ranges never overlap.
- R-FEE-3: FALL tuition for 8 of the 20 programs was revised by +5% effective 2026-07-01. Version V1 ends
  2026-06-30, V2 starts 2026-07-01. FALL invoices issue on 2026-08-10, so they must use V2. This is the
  "term-specific fees are correct" test.

### 5.3 Billing (R-BILL)

- R-BILL-1: one invoice per enrollment, issued on the term's issue date, with one FEE line per eligible
  fee schedule row, in fee-type order as listed in 5.2. `line_no` starts at 1.
- R-BILL-2: fee waivers are WAIVER lines (negative) that point at the FEE line they reduce.
  STAFF_WARD waives 100% of TUITION; SIBLING waives 10% of TUITION; HARDSHIP waives 100% of LIBRARY,
  TECHNOLOGY and EXAM. A student has at most one waiver type.
- R-BILL-3: `invoice.total_paise` = sum of all its lines (charges positive, credits negative). It is
  never typed in; it is computed.
- R-BILL-4: a line's outstanding amount = its amount + credits pointing at it - allocations to it.
  Only charge lines (FEE, LATE_FEE) can receive allocations.

### 5.4 Scholarships (R-SCH)

Schemes (master data):

| Scheme | Criteria (all must hold) | Award |
|---|---|---|
| MERIT_GOLD | gpa >= 9.00 | 50% of eligible fees |
| MERIT_SILVER | gpa >= 8.00 | 25% of eligible fees |
| NEED_BASED | income_band = LOW and gpa >= 6.00 | 40% of eligible fees |
| SPORTS | sports_quota and gpa >= 5.50 | fixed INR 30,000 |
| INTL_EXCELLENCE | residency = INTERNATIONAL and gpa >= 8.50 | 20% of eligible fees |

- R-SCH-1: eligible fees = sum of the invoice's scholarship-eligible FEE lines (TUITION, LAB) minus
  waivers on those lines.
- R-SCH-2: every application gets an Eligibility row with the attribute values it was judged on, the
  decision and a reason code (`MEETS_CRITERIA`, `GPA_BELOW_MIN`, `INCOME_BAND_NOT_LOW`,
  `NOT_SPORTS_QUOTA`, `NOT_INTERNATIONAL`, `NOT_ENROLLED`, `NO_ELIGIBLE_FEES`, `SUPERSEDED`).
- R-SCH-3: a student gets at most one award per term. If eligible under several schemes, the one with
  the largest computed amount wins; ties go to the scheme listed first above. The losing eligible
  applications are recorded as INELIGIBLE with reason `SUPERSEDED`.
- R-SCH-4: awarded amount = min(computed amount, eligible fees). A scholarship can never exceed the
  eligible fees. Percentages round half up to the paise.
- R-SCH-5: the award is applied as SCHOLARSHIP credit lines, TUITION first and then LAB, each pointing at
  the line it reduces and never exceeding that line's amount net of waivers.
- R-SCH-6: if the enrollment is cancelled before the term starts, the award is REVOKED and its credit is
  netted out by the cancellation adjustment.

### 5.5 Payments and allocation (R-PAY)

- R-PAY-1: a payment belongs to a student. On receipt it is allocated to that student's open charge
  lines: invoices by due date oldest first, within an invoice by `line_no`.
- R-PAY-2: an allocation never exceeds the line's outstanding amount, and the allocations of one
  payment never add up to more than the payment.
- R-PAY-3: whatever is not allocated is unapplied credit (an overpayment). It stays on the payment and
  is allocated to the student's next invoice on that invoice's issue date.
- R-PAY-4: allocation ids are `ALLOC-<payment_id>-NN` in allocation order.
- R-PAY-5: unapplied credit that is still unused 30 days after receipt, when the student has no open
  invoice, is refunded (reason OVERPAYMENT).

### 5.6 Late fees (R-LATE)

- R-LATE-1: if an invoice still has an outstanding amount at the end of due date + 7 days (grace), a
  LATE_FEE line is added on due date + 8 days.
- R-LATE-2: late fee = 2% of the outstanding amount at that moment, at least INR 500 and at most
  INR 5,000, rounded half up to the paise.
- R-LATE-3: at most one late fee per invoice. None on CANCELLED or VOID invoices, and none when the
  enrollment was withdrawn before the late-fee date.

### 5.7 Withdrawals, cancellations and refunds (R-WD, R-REF)

- R-WD-1: CANCELLED = left before the term start date. 100% of net charges are reversed by an
  ADJUSTMENT line; invoice status becomes CANCELLED; scholarship is REVOKED.
- R-WD-2: WITHDRAWN = left on or after the term start date. Refundable share of net charges
  (charges - waivers - scholarship, excluding late fees): days 0 to 14 of term 75%, days 15 to 30 50%,
  after day 30 0%. The share is posted as ADJUSTMENT lines (negative), one per reduced charge line.
- R-REF-1: after an adjustment, if the invoice is overpaid (allocations exceed what is now owed), the
  excess is de-allocated (a negative allocation row, so history is kept) and refunded (reason WITHDRAWAL
  or CANCELLATION).
- R-REF-2: a refund can never exceed the student's net paid amount (payments - earlier refunds) at that
  moment.
- R-REF-3: a refund is created APPROVED and becomes PAID 3 days later.

### 5.8 Ledger and balance (R-LED)

Every money movement posts one `ledger_entry` (append-only):

| entry_type | Sign | Source |
|---|---|---|
| CHARGE | + | FEE line |
| LATE_FEE | + | LATE_FEE line |
| WAIVER | - | WAIVER line |
| SCHOLARSHIP | - | SCHOLARSHIP line |
| ADJUSTMENT | - | ADJUSTMENT line |
| PAYMENT | - | payment (the full amount received) |
| REFUND | + | refund |

- R-LED-1: student balance = sum of the student's ledger entries. Positive means the student owes money;
  negative means the institution holds credit.
- R-LED-2: `student_balance` stores the stated figures (charged, credits, paid, refunded, balance) as of
  2026-10-22, derived from the same source rows. It must equal the ledger.
- R-LED-3: balance also equals (sum of invoice totals) - (payments) + (refunds). Three independent
  routes to the same number; validation checks all three agree.

### 5.9 Invoice status (derived, R-STAT)

In order: VOID if voided; CANCELLED if the enrollment was cancelled; PAID if outstanding is 0;
OVERDUE if outstanding > 0 and the as-of date is past the due date; PARTIALLY_PAID if something was
allocated; otherwise ISSUED.

## 6. Synthetic data

One generator, parameterised by scale and seed. It is a simulation: it walks the calendar and calls the
`domain/` functions, so every derived value comes from the rules.

| Scale | Students | Programs | Invoices | Scholarship awards | Payments |
|---|---|---|---|---|---|
| starter | 500 | 20 | 1,500 | 750 | 2,500 |
| full | 10,000 | 20 | 30,000 | 15,000 | 50,000 |

How the exact counts are reached without random outcomes:

- Invoices: every student enrolls in all three terms, so invoices = students x 3. Students who leave
  still have their invoice (cancelled or adjusted).
- Scholarship awards: applications are filed in a seeded order and each is judged by R-SCH. Filing stops
  when the award target is reached. Ineligible applications remain as INELIGIBLE Eligibility rows.
- Payments: each invoice gets a payment behaviour (FULL_ON_TIME, INSTALMENTS, PARTIAL, LATE_FULL,
  OVERPAY, NONE) drawn from a seeded distribution. The plan is then topped up to the target by splitting
  seeded-chosen payments into two instalments, which changes the count and not the money.

Order of generation: program, term, scholarship_scheme, student, fee_schedule (masters); enrollment,
invoice, invoice_line, eligibility, scholarship, payment, payment_allocation, late fees, withdrawals,
refund (dependents); ledger_entry, student_balance, event (derived); then anomalies; then ground truth.

Coverage the baseline must contain: partial payments, overpayments, fee waivers, term withdrawals,
pre-term cancellations, late fees, unpaid invoices, instalments, both fee versions.

Reproducibility: all randomness flows from `random.Random` sub-streams keyed by seed and name
(`rand.stream("payments")`), so adding a draw in one area does not shift another. Rows are written in
primary-key order with fixed column order, `\n` line endings and UTF-8. `manifest.json` records row
counts and SHA-256 per file. `cli repro` generates twice and compares.

### 6.1 Labelled anomalies

Injected after the valid baseline, each on its own set of students (an anomaly never touches a student
that carries another one). Derived values are **not** recomputed after injection; that disagreement is
what a detector must find. Labels go to `ground_truth` only.

| issue_type | What is injected | Expected decision | starter | full |
|---|---|---|---|---|
| ALLOC_EXCEEDS_PAYMENT | an extra allocation row so a payment's allocations exceed its amount | REVERSE_ALLOCATION | 8 | 150 |
| SCHOLARSHIP_EXCEEDS_ELIGIBLE | scholarship amount and credit line raised above eligible fees | CAP_SCHOLARSHIP | 6 | 120 |
| DUPLICATE_INVOICE | a second invoice for the same enrollment with the same lines | VOID_DUPLICATE | 5 | 100 |
| REFUND_EXCEEDS_NET_PAID | a refund larger than payments minus earlier refunds | BLOCK_REFUND | 4 | 80 |
| BALANCE_LEDGER_MISMATCH | `student_balance.balance_paise` moved away from the ledger sum | RECOMPUTE_BALANCE | 8 | 150 |

Ground truth columns: `gt_id, issue_type, entity_type, entity_id, student_id, expected_decision,
expected_value_paise, details`. Stored in `data/<scale>/ground_truth/` and in the `gt` database schema.
No input table has a column that hints at an anomaly.

### 6.2 Validation (`cli validate`)

Runs on the generated files, no database needed. Each check has an id, a count of rows checked and a
list of violations. Violations that match a ground-truth label are "expected"; anything else fails.

1. Primary keys unique and matching their id pattern.
2. Every foreign key resolves.
3. Enum columns hold only allowed values; required columns are present.
4. Date order: issue <= due; effective_from <= effective_to; refund not before the payment; term dates.
5. Arithmetic: invoice total = sum of lines; allocations per payment <= amount; allocations per line <=
   line net; scholarship <= eligible fees; refund <= net paid; late fee formula; balance three ways
   (R-LED-3).
6. Lifecycle: every status is reachable through `event` rows by allowed transitions only.
7. Duplicates: one invoice per enrollment; one award per student and term; no repeated natural keys.
8. Volume targets met for the scale.
9. Leak check: no input table contains `issue_type`, `ground_truth`, `anomaly` or `expected_` columns.

Output: `reports/<scale>/validation_summary.json`.

### 6.3 Detection and evaluation (`cli reconcile`)

Detectors recompute everything from source rows and write `exception` rows (type, entity, student,
amounts expected and found, recommended decision). They never read ground truth. Evaluation then
compares exceptions with ground truth per issue type and overall: true positives, false positives,
false negatives, precision, recall, F1. Business metrics: billed, waived, scholarships, collected,
refunded, outstanding, collection rate, reconciliation rate (students whose stated balance equals the
ledger), late-fee incidence, award distribution by scheme.

Output: `reports/<scale>/evaluation.json`.

## 7. API (`/api/v1`)

Conventions: JSON; money as integer paise; errors as `{"error": {"code", "message", "request_id"}}`;
list endpoints use keyset pagination (`?after=<id>&limit=50`, max 200); every response carries
`X-Request-ID`; OpenAPI at `/docs`.

| Method and path | Roles | Purpose |
|---|---|---|
| POST `/auth/login`, GET `/auth/me` | all | sign in, identity |
| POST `/auth/forgot`, POST `/auth/reset` | public | email a reset link; set a new password with it |
| GET `/metrics/overview` | staff | headline figures, by term and by program |
| GET `/students` | staff | search and list, with balance and flags |
| GET `/students/{id}` | staff, own learner | profile, enrollments, invoices, balance (stated and ledger) |
| GET `/students/{id}/ledger` | staff, own learner | ledger entries with running balance |
| GET `/students/{id}/events` | staff, own learner | state history |
| GET `/invoices/{id}` | staff, own learner | lines, credits, allocations per line, status history |
| GET `/programs`, GET `/terms`, GET `/fee-schedules` | staff | fee matrix by program and term |
| GET `/scholarship-schemes`, GET `/scholarships`, GET `/eligibility` | staff | criteria, awards, decisions with reasons |
| POST `/payments` | SUPPORT | record a payment; allocates by R-PAY in one transaction; idempotent on `Idempotency-Key` |
| POST `/enrollments/{id}/withdraw` | ACADEMIC_ADMIN | applies R-WD and R-REF in one transaction |
| GET `/exceptions` | SUPPORT, PLATFORM_ADMIN | queue with filters |
| POST `/exceptions/{id}/resolve` | SUPPORT | RESOLVED or DISMISSED with a note; writes an event |
| GET `/quality` | PLATFORM_ADMIN | validation summary, detection metrics, repro result |
| GET `/healthz`, GET `/readyz` | public | liveness, database readiness |

"staff" means every role except LEARNER; INSTRUCTOR is limited to its own program. Writes run in one
database transaction, lock the student row (`SELECT ... FOR UPDATE`) so two payments for the same
student cannot both allocate the same outstanding amount, and append ledger and event rows in the same
transaction.

## 8. Frontend

A ruled "register paper" visual system: ruled paper, Hanken Grotesk for text, Instrument Serif
for headings, 1px rules, red margin line, `.stamp` status labels, `table.register`, light and dark
themes, scroll reveals from `motion.ts` (off with `?motion=off`).

Signature moment: on a student whose stated balance disagrees with the ledger, the stated figure gets
the hand-drawn red strike and the ledger figure inks in beside it.

| Page | Route | Roles | Shows |
|---|---|---|---|
| Login | `/login` | all | sign in, demo role shortcuts |
| Overview | `/` | staff | billed, collected, outstanding, scholarships, reconciliation rate; by term and program |
| Students | `/students` | staff | searchable register with balance and status stamps |
| Student ledger | `/students/:id` | staff, learner | enrollments, invoices, ledger with running balance, event timeline |
| Invoice | `/invoices/:id` | staff, learner | each line with its credits and the payments allocated to it |
| Fee schedules | `/fees` | staff | program by term matrix, versions and effective dates |
| Scholarships | `/scholarships` | staff | schemes and criteria, awards, eligibility decisions with reasons |
| Exceptions | `/exceptions` | SUPPORT, PLATFORM_ADMIN | queue by type; evidence; resolve or dismiss |
| Data quality | `/quality` | PLATFORM_ADMIN | validation checks, precision and recall per issue type, repro checksums |
| My account | `/me` | LEARNER | own balance, invoices, awards |

Engineering: typed API client generated from the backend's OpenAPI document, TanStack Query for
caching, route-level code splitting, visible focus states and real table semantics, layouts that work
from 360px wide.

## 9. Deployment

Server `vbs` (Ubuntu 22.04, 1 GB RAM), domain `studease.is-cool.dev`.

```
nginx :443 (certbot)  --->  /opt/studease/web        static frontend build
                      --->  127.0.0.1:8200           uvicorn, systemd unit studease-api (user studease)
PostgreSQL 14 on localhost: role studease, databases studease and studease_test (CONNECT revoked from PUBLIC)
```

`deploy/deploy.sh`: ship `git archive HEAD` over SSH, `uv sync --frozen`, `alembic upgrade head`,
restart, wait for `/readyz`, roll back to the previous release if it does not come up. nginx adds
HSTS, `X-Content-Type-Options`, `Referrer-Policy`, a content security policy and gzip.

Local development needs no server: a throwaway PostgreSQL cluster in `.pgdata/` on port 15433
(`make db-up`), then `make api` and `make web`.

## 10. Quality bar

- Tests: unit tests for every domain rule (pure, fast); generator tests (counts, determinism, FK
  integrity); detector tests (each anomaly type found, clean data yields nothing); API tests against a
  real Postgres test database; frontend unit tests for formatting.
- CI on every push: ruff, pytest, generate starter, validate, repro check, frontend typecheck, lint and
  build.
- Bulk load with `COPY`; indexes on every foreign key the API filters by; keyset pagination; no N+1
  queries.
- Structured JSON logs with request ids; `/readyz` checks the database.
- No secrets in the repository; `.env.example` documents every variable.

## 11. Assumptions and known limits

- Currency is INR; one institution; one calendar year (2026); every student enrolls in all three terms.
- One late fee per invoice rather than a recurring monthly charge.
- Payments are never reversed (no bounced-payment flow).
- Refund policy uses term days, not credit hours.
- Names and emails are synthetic (`@example.edu`); no real person's data is used; no external dataset.
- The browser keeps the JWT in `localStorage`. A script injection could read it; the content security
  policy and React's escaping are the mitigations. An httpOnly cookie with CSRF protection is the upgrade.

## 12. Security

Threats considered: a visitor to the public demo, a signed-in learner trying to read or change another
account, a bug in the backend writing a forbidden row, and private details leaking through the public
repository.

| Id | Control | Where it is enforced |
|---|---|---|
| S-1 | **No SQL injection**: every query uses bound parameters; no string-built SQL from request input | `api/*.py`, reviewed by a test that greps for f-strings in `text(` calls |
| S-2 | **Object-level authorisation**: a learner's `student_id` is read from the token; staff routes check role; an instructor is filtered to its own `program_id` | `api/deps.py` `require_role`, `scope_student` |
| S-3 | **Password hashing**: scrypt (n=2^14, r=8, p=1, 16-byte salt), compared in constant time | `security.py` |
| S-4 | **Uniform sign-in failure**: unknown email and wrong password return the same 401 body. Timing equalisation is deferred (see "Deferred by decision" below) | `api/auth.py` |
| S-5 | **Login throttling**: deferred by decision while the system is under test (see below) | not built |
| S-6 | **JWT secret guard**: with `ENV=prod` the app refuses to start if `JWT_SECRET` is the default or shorter than 32 characters, or if `DEMO_PASSWORD` is unset or shorter than 12 | `config.py` `Settings.check()` |
| S-7 | **Token rules**: HS256 only (algorithm pinned on decode), `exp` 8 hours, `sub`, `role`, `student_id`, `program_id` claims; a disabled user is rejected on every request | `security.py`, `api/deps.py` |
| S-8 | **Public demo accepts writes (accepted risk)**: demo logins can record payments, withdraw enrollments and resolve exceptions on the live site, so reviewers can exercise the whole workflow. All data is synthetic and every write is attributed in `event`; `make load` restores the seeded state | owner decision |
| S-9 | **Idempotency scoped to the caller**: the key is stored as (`app_user_id`, key) with a hash of the request body; the same key with a different body is 422; another user's key never matches | `api/payments.py`, `idempotency_key` table |
| S-10 | **Input limits**: Pydantic models with `extra="forbid"`; amounts 1 to 10,000,000,00 paise; page `limit` 1 to 200; ids must match their pattern; request body capped at 64 KB by nginx | `api/*.py`, `deploy/nginx-studease.conf` |
| S-11 | **CORS**: only the origins in `CORS_ORIGINS` (the site itself in production); no wildcard; no credentials mode | `main.py` |
| S-12 | **Error hygiene**: clients get the error envelope and a request id, never a stack trace; passwords, tokens and `Authorization` headers are never logged | `api/errors.py`, `logging.py` |
| S-13 | **Database least privilege**: role `studease` owns only its two databases; `CONNECT` revoked from `PUBLIC`; Postgres listens on localhost only; local dev cluster binds 127.0.0.1 | `docs/deploy.md`, `Makefile` |
| S-14 | **Database as second line**: `CHECK`, `FOREIGN KEY` and `UNIQUE` constraints reject forbidden rows even if the backend is wrong | `schema.py` |
| S-15 | **Concurrency safety**: writes lock the student row with `SELECT ... FOR UPDATE` inside one transaction, so two payments cannot allocate the same outstanding amount | `api/payments.py`, `api/enrollments.py` |
| S-16 | **Transport and headers**: HTTPS only with HSTS; `X-Content-Type-Options: nosniff`; `Referrer-Policy: strict-origin-when-cross-origin`; `X-Frame-Options: DENY`; content security policy `default-src 'self'` with fonts from Google Fonts | `deploy/nginx-studease.conf` |
| S-17 | **Service hardening**: uvicorn bound to 127.0.0.1; systemd unit runs as non-root user `studease` with `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp` | `deploy/studease-api.service` |
| S-18 | **Secrets**: none in the repository; `.env` is git-ignored; `.env.example` documents every variable with no values | `.gitignore`, `backend/.env.example` |
| S-19 | **Supply chain**: `uv.lock` and `package-lock.json` committed; installs use `--frozen` and `npm ci`; GitHub Actions pinned to a major version tag | `.github/workflows/ci.yml` |
| S-20 | **Public repository hygiene**: before any push, the prompt history and every committed file are scanned for email addresses other than `@example.edu`, IP addresses, host names, passwords and local user paths; findings are redacted | `scripts/scrub_check.py`, run in CI |
| S-21 | **Data privacy**: all people are synthetic; emails use the reserved `example.edu` domain; no external dataset | `datagen/people.py` |
| S-22 | **Outbound mail**: SMTP over STARTTLS with an existing sending account; credentials only in the server `.env`; mail is skipped when SMTP is not configured and is never sent to `@example.edu` (synthetic) addresses; message bodies never contain a password or a token other than the single-use reset link | `mail.py` |
| S-23 | **Password reset**: `POST /auth/forgot` always answers 202 with the same body; the link carries a signed token valid 30 minutes and bound to the current password hash, so it works once | `api/auth.py`, `security.py` |

Deferred by decision (2026-11-14, owner): login throttling per email and per IP, and timing equalisation
for unknown emails. Reason: the system is being tested by hand and lockouts get in the way. To add later:
a `login_attempt` table, 5 failures per email and 20 attempts per IP per 15 minutes, 429 with
`Retry-After`, and one scrypt against a dummy hash for unknown emails.

### Mail

`mail.send(to, subject, text)` is used in two places: the password-reset link, and a receipt to the
learner's login email when a payment is recorded. Sending happens after the database transaction commits
and a mail failure is logged and never fails the request.
