# StudEase

Tuition and fees, scholarship eligibility and payments, and student-balance reconciliation, with a synthetic data
generator, five labelled anomalies, a validator, detectors and a working three-tier application.

- **What it does:** bills each student from versioned fee schedules, decides scholarships by published rules, allocates
  payments to the oldest due line first, handles withdrawals and refunds, and proves every balance three ways
  (stated balance = sum of the append-only ledger = invoices - payments + refunds).
- **Data:** 10,000 students, 20 programs, 30,000 invoices, 15,000 awards, 50,000 payments from fixed seed
  `20261022`; the same generator runs at a small "starter" scale. All people are synthetic (`@example.edu`).
- **App:** `frontend/` (React + TypeScript), `backend/` (FastAPI), `database/` (PostgreSQL schema and migrations).
  Three tiers in three folders; the business rules live in a pure `backend/app/domain/` package with no framework in it.

**Live demo:** https://studease.is-cool.dev. Sign in as `learner@`, `instructor@`, `academic@`, `support@` or `admin@example.edu` with the
demo-only password `Studease-Demo-2026`, or create your own learner account from the sign-in page. The demo accepts writes (payments, enrolments,
withdrawals, resolutions) by design; all data is synthetic.

Start with [docs/walkthrough.md](docs/walkthrough.md) (one student followed end to end) or
[docs/architecture.md](docs/architecture.md) (every rule, with its id).

## Screens

| | |
|---|---|
| ![Sign in](docs/screenshots/login.png) | ![Learner account](docs/screenshots/learner-account.png) |
| Sign in, with a visible **Create a new account** button | Learner account: balance cards, money by kind, balance over time, pay now |
| ![Overview](docs/screenshots/overview.png) | ![Student](docs/screenshots/student-detail.png) |
| Overview for staff: monthly line chart, status donut, term bars | Student page for an academic admin: edit details, assign scholarship, invoice downloads |
| ![Fee schedules](docs/screenshots/fee-schedules.png) | ![Users](docs/screenshots/users.png) |
| Fee schedules with **Publish a new fee version** | Platform admin: create and disable accounts |
| ![Scholarships](docs/screenshots/scholarships.png) | ![Exceptions](docs/screenshots/exceptions.png) |
| Awards by scheme (count and money) | Exception queue with a by-type donut |
| ![Add student](docs/screenshots/add-student.png) | ![Dark mode](docs/screenshots/overview-dark.png) |
| Staff data entry | Dark theme |

Also in `docs/screenshots/`: `learner-enroll.png`, `students.png`, `data-quality.png`.

## Quick start

**Windows, one step:** run [`run.bat`](run.bat). It checks the tools, installs, starts the database, loads the data and opens the app
(details and troubleshooting in [SETUP.md](SETUP.md)). Or follow the manual steps below.

Prerequisites: Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 20+, PostgreSQL 14+ (the client and server
binaries; the project creates its own throwaway cluster, it never touches an existing one).

```bash
python scripts/dev.py install      # backend and frontend dependencies
python scripts/dev.py db-up        # local PostgreSQL on 127.0.0.1:15433 (created on first use)
python scripts/dev.py migrate      # schema, from database/migrations
cp backend/.env.example backend/.env   # then set DEMO_PASSWORD (any value; it is the demo login password)
python scripts/dev.py load         # loads the starter data and seeds one demo login per role
python scripts/dev.py api          # API on http://127.0.0.1:8000  (docs at /api/v1/docs)
python scripts/dev.py web          # app on http://localhost:5173  (second terminal)
```

`make <command>` does the same where `make` exists; `python scripts/dev.py help` lists every command. Windows,
macOS and Linux are all supported (the runner is standard-library Python).

Sign in at `http://localhost:5173` with `learner@`, `instructor@`, `academic@`, `support@` or `admin@example.edu`
and the `DEMO_PASSWORD` you set, or use **Create a learner account** on the sign-in page. Each role sees and can do different
things ([architecture §3](docs/architecture.md), [docs/frontend.md](docs/frontend.md)).

To load the full 10,000-student dataset instead: `SCALE=full python scripts/dev.py load` (about 30 seconds).

### Configuration (`.env`)

Settings come from environment variables, read from `backend/.env` (git-ignored; `backend/.env.example` lists every
variable with no values). Nothing secret is ever committed. In production (`ENV=prod`) the API refuses to start
with a default or short `JWT_SECRET` or `DEMO_PASSWORD`. Mail is optional: set the `SMTP_*` variables to enable
password-reset links and payment receipts; `MAIL_TEST_TO` redirects mail meant for synthetic users to one test inbox.

## Tests

```bash
python scripts/dev.py test            # backend: 230+ tests (domain rules, data, API, security, loader)
cd frontend && npm test               # frontend unit tests
python scripts/dev.py lint            # ruff
cd frontend && npx tsc -b             # TypeScript
python scripts/scrub_check.py         # the public-repo hygiene check
```

The database tests need the local cluster from `db-up` and skip themselves, with a message, when it is not running.
How the tests are organised, and what each proves: [docs/testing.md](docs/testing.md).

## Verify the data

```bash
python scripts/dev.py data         # generate (SCALE=starter|full), write CSV/JSON/SQL and the manifest
python scripts/dev.py validate     # nine checks, every violation classified: explained by a label or unexpected
python scripts/dev.py repro        # generate twice, compare row counts and SHA-256 checksums
python scripts/dev.py reconcile    # run the detectors (they never see the ground truth) and score them
```

| | Starter | Full |
|---|---|---|
| Rows generated | 50,339 | 1,004,038 |
| Students / invoices / awards / payments | 500 / 1,500 / 750 / 2,500 | 10,000 / 30,000 / 15,000 / 50,000 |
| Labelled anomaly cases | 31 | 600 |
| Validation | passed, 0 unexpected violations | passed, 0 unexpected violations |
| Two runs identical | yes (all tables) | yes (all tables, matches the committed manifest) |
| Detector precision / recall | 1.0 / 1.0 | 1.0 / 1.0 |
| Collection rate / late-fee incidence / reconciliation rate | 0.790 / 0.294 / 0.984 | 0.792 / 0.281 / 0.985 |

Reports are committed in `reports/<scale>/`; data is in `data/<scale>/` (the full set as compressed CSV with a
manifest). The data dictionary and entity diagram are generated from the schema: [docs/data_dictionary.md](docs/data_dictionary.md),
[docs/erd.md](docs/erd.md).

### The five labelled anomalies

| Anomaly | What is wrong | How it is caught |
|---|---|---|
| `ALLOC_EXCEEDS_PAYMENT` | allocations add up to more than the payment | per-payment sum of allocations vs amount |
| `SCHOLARSHIP_EXCEEDS_ELIGIBLE` | award larger than the scholarship-eligible fees | award vs recomputed eligible fees (R-SCH-1) |
| `DUPLICATE_INVOICE` | one enrollment billed twice | more than one live invoice for an enrollment |
| `REFUND_EXCEEDS_NET_PAID` | refund larger than payments minus earlier refunds | running net paid at the approval date (R-REF-2) |
| `BALANCE_LEDGER_MISMATCH` | stated balance differs from the ledger | the three-way balance identity (R-LED-3) |

Ground truth is stored separately (`data/*/ground_truth/`, and the `gt` schema in the database) and is never a column of
an input table; a test fails if a leak word appears in any input table.

## What makes it more than a prototype

- **Integer money:** paise and basis points everywhere, round half up, one rule for every percentage. No floats near money.
- **Append-only history:** the ledger and the event table are only ever added to; reversals are negative rows.
- **Database as a second line of defence:** primary and foreign keys, `CHECK` constraints for every enumeration and
  sign rule; the backend cannot write a forbidden row even if it has a bug.
- **A complete learner journey:** create an account, enrol in a term (fee preview, scholarship checklist with the reason for every scheme
  you do not meet), pay, withdraw, see awards and fees, export a statement, change your password. Staff can enrol a student through the same code.
- **Export everywhere:** CSV (spreadsheet-safe: UTF-8 BOM, formula neutralisation), JSON and Print / PDF on every list and account; lists export
  the whole filtered set, not the visible page.
- **A designed interface, not a template:** cut-corner and folder-tab cards, wavy navigation, pill buttons, scroll and pointer
  motion, charts that draw in, skeleton cards with the real shapes while data loads, a top progress bar, a splash, toasts, light and dark themes
  ([docs/frontend.md](docs/frontend.md)).
- **Safe writes:** a payment is idempotent (`Idempotency-Key`, scoped to the caller), takes a row lock on the student and
  an advisory lock for id numbering, and writes the payment, allocations, ledger, events and balance in one transaction.
- **Security:** scrypt passwords, pinned-algorithm JWTs, role checks in one place, object-level scoping, bound
  parameters only (a test fails if SQL is built from strings), strict input models, error envelope with request ids,
  CORS allow-list, security headers, hardened service unit. The full list (S-1 to S-23) is in [architecture §12](docs/architecture.md).
- **A real error experience:** the app has its own 404, 403 and crash pages (route error boundary); the API always
  answers with a JSON error envelope and an `X-Request-ID`; nginx serves a static page ([frontend/public/50x.html](frontend/public/50x.html))
  when the API is down; an expired session returns you to sign-in.
- **Polish:** per-page titles and meta descriptions, Open Graph tags, a hand-drawn favicon and app icons, a web manifest, `robots.txt`,
  light and dark themes, keyboard focus styles and a skip link, reduced-motion support, mobile layout (360 px and up).
- **Deployment as code:** [deploy/](deploy) holds the nginx config, the systemd unit and a script with health check and
  one-command rollback; CI runs lint, tests, the docs-freshness check, the reproducibility check and the hygiene scan.
  How it is deployed, step by step: [docs/deploy.md](docs/deploy.md).

## Repository map

```
frontend/   React 19 + Vite + TypeScript + Tailwind 4 (pages, design system, unit tests)
backend/    FastAPI app (app/api, app/domain, app/datagen, app/engine), tests/, pyproject.toml, uv.lock
database/   PostgreSQL schema as Alembic migrations, seed SQL for the starter data
data/       generated datasets, manifests and ground truth
reports/    validation, reproducibility and evaluation reports
deploy/     nginx, systemd, deploy script
scripts/    dev.py (cross-platform task runner), scrub_check.py
docs/       architecture, practices, decisions, testing, deploy, data dictionary, ERD, walkthrough
prompts/    prompt history and the statement of AI use
```

## Honest limits

- **Perfect detection is by construction.** The detectors do not read the ground truth, but they recompute the same
  rules the generator used, so precision and recall of 1.0 show the rules are implemented consistently. They do not
  show that the detectors would find unknown faults in real data. Treat the score as a regression test, not evidence of generalisation.
- **Dates are frozen.** Every status and balance is stated as of 2026-09-05 (`AS_OF`); new payments and withdrawals are
  dated that day. There is no scheduler issuing invoices or late fees as time passes.
- **Writes are serialised.** One advisory lock orders id allocation, so write throughput is bounded to one transaction at a
  time. Ample for a back-office tool; database sequences would lift it ([docs/decisions.md](docs/decisions.md)).
- **Login throttling and timing equalisation are deliberately not built yet** (owner decision while testing); a test
  pins their absence so adding them is a conscious change.
- **Currency is INR in paise** by assumption; the brief does not name one.
- The public demo accepts writes by design; all data is synthetic and the loader restores the seeded state.

## How AI was used

AI assistance (Claude) was used for planning, writing code and tests, and documentation, as the brief allows. The
design decisions, the rules, the labelling scheme and the review of every result were mine. Prompt history and a plain
account of what was generated, what I changed and how I checked it are in [prompts/](prompts). I can walk through any file.

## Documents

| | |
|---|---|
| [docs/architecture.md](docs/architecture.md) | the specification: tiers, entities, every business rule, data generation, API, security |
| [docs/practices.md](docs/practices.md) | each engineering practice used, where, why and how far |
| [docs/decisions.md](docs/decisions.md) | the choices that could have gone another way, and the reasons |
| [docs/testing.md](docs/testing.md) | the test strategy and what each group proves |
| [docs/frontend.md](docs/frontend.md) | the design system, motion, loading states, pages by role, exports, error pages, accessibility |
| [SETUP.md](SETUP.md) | install, run, settings, checks and troubleshooting; `run.bat` does it in one step |
| [docs/permissions.md](docs/permissions.md) | the role-by-route permission matrix, generated from the route guards |
| [docs/edge-cases.md](docs/edge-cases.md) | every edge case and negative scenario, what enforces it, the test that proves it |
| [docs/deploy.md](docs/deploy.md) | production setup, deploy, rollback, mail, operations |
| [docs/walkthrough.md](docs/walkthrough.md) | one student, every record, generated from the data |
| [docs/data_dictionary.md](docs/data_dictionary.md), [docs/erd.md](docs/erd.md) | generated from the schema |
| [database/README.md](database/README.md) | the database tier |
