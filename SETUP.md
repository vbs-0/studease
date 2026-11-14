# Setup and run

Short version for Windows: install the four tools in the table, then double-click **`run.bat`** (or run it in a terminal). It checks everything,
installs what is missing, starts the database, loads the data once, starts the API and the web app, and opens the browser.

| Tool | Version | Get it | Check |
|---|---|---|---|
| Python | 3.12 or newer | <https://www.python.org/downloads/> | `python --version` |
| uv (Python package manager) | any recent | `pip install uv` or <https://docs.astral.sh/uv/> | `uv --version` |
| Node.js (with npm) | 20 or newer | <https://nodejs.org> | `node --version` |
| PostgreSQL | 14 or newer | <https://www.postgresql.org/download/> | `pg_ctl --version` (or set `PGBIN` to its `bin` folder) |

Nothing else is needed: no Docker, no accounts, no internet after the first install. The database is a throwaway cluster in `.pgdata/` inside
the project (trust authentication, `127.0.0.1` only, port 15433), so it never touches an existing PostgreSQL on the machine.

## What `run.bat` does

| Step | What happens | Safe to repeat? |
|---|---|---|
| 1. Check tools | looks for Python, uv, Node, npm and the PostgreSQL binaries; names every missing one and stops | yes |
| 2. Install | `uv sync` (backend) and `npm ci` (frontend), only when `backend/.venv` or `frontend/node_modules` is missing; creates `backend/.env` from `.env.example` if absent | yes |
| 3. Database | creates `.pgdata/` the first time, starts PostgreSQL, creates the `studease` role and the `studease` and `studease_test` databases | yes |
| 4. Tables | `alembic upgrade head` creates or upgrades the schema | yes |
| 5. Data | loads the committed starter dataset (500 students, about 50,000 rows) and the five demo logins, once; remembered by `.pgdata/loaded.flag` | yes (skipped after the first time) |
| 6. Run | opens two windows (API on `http://127.0.0.1:8000`, web on `http://localhost:5173`), waits until the web app answers, opens the browser | yes |

Other commands: `run.bat stop` (close the API and web windows and stop the database), `run.bat test` (backend and frontend tests).

## Sign in

Open <http://localhost:5173>. The demo logins are one per role:

| Email | Role | Sees |
|---|---|---|
| `learner@example.edu` | Learner | own account, enrol, pay, scholarships, fees |
| `instructor@example.edu` | Instructor | students of their program, enrolment status only |
| `academic@example.edu` | Academic admin | overview, students, fee versions, awards, withdrawals |
| `support@example.edu` | Support | overview, payments, add students, exception queue |
| `admin@example.edu` | Platform admin | everything, users, data quality |

The password is `DEMO_PASSWORD` from `backend/.env`; when that value is empty the default `demo-password-for-local-use` applies. Anyone can also
create a learner account with **Create a new account** on the sign-in page. What each role may do is in [`docs/permissions.md`](docs/permissions.md).

## Settings (`backend/.env`, git-ignored)

Every value is optional locally. The ones worth knowing:

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | the `db-up` database | where the API connects |
| `DEMO_PASSWORD` | `demo-password-for-local-use` | password of the five demo logins (set before the first load, or reload) |
| `SEED` | `20261022` | seed of the data generator; the same seed always gives identical data |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` | empty | outbound mail for receipts and password reset; with them empty the app logs a line instead and still works |
| `ENV` | `dev` | `prod` refuses to start with default secrets (`JWT_SECRET`, `DEMO_PASSWORD`, `CORS_ORIGINS`, `APP_URL` must be set) |

Never commit `.env`; `scripts/scrub_check.py` fails if a secret or a real address is about to be committed.

## The same thing by hand (any operating system)

```bash
python scripts/dev.py install      # uv sync + npm ci
python scripts/dev.py db-up        # cluster, role, databases
python scripts/dev.py migrate      # tables
python scripts/dev.py load         # starter data + demo logins   (SCALE=full for 10,000 students: first run python scripts/dev.py data)
python scripts/dev.py api          # terminal 1: http://127.0.0.1:8000  (API docs at /api/v1/docs)
python scripts/dev.py web          # terminal 2: http://localhost:5173
```

`make <command>` forwards to the same runner. macOS and Linux need no `run.bat`; use the commands above (PostgreSQL from `brew install postgresql`
or `apt install postgresql`, and `PGBIN` if the binaries are not on the `PATH`).

## Check that it works

```bash
python scripts/dev.py test                 # 318 backend tests (needs the database from db-up)
cd frontend && npx vitest run && npx tsc -b   # frontend tests and type check
python scripts/dev.py lint                 # ruff
python scripts/dev.py docs                 # regenerate the generated docs; `... docs --check` only verifies
python scripts/scrub_check.py              # no secrets or real addresses in the repository
python scripts/dev.py all                  # generate, validate, reproduce and reconcile the data end to end
```

## Deploy to a server

Covered step by step in [`docs/deploy.md`](docs/deploy.md): `DEPLOY_HOST=<ssh host> ./deploy/deploy.sh` builds the release, uploads it,
runs migrations, restarts the service and checks health; `./deploy/deploy.sh rollback` returns to the previous release.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `run.bat` says `MISSING: ...` | install that tool, open a **new** terminal (so `PATH` refreshes), run again |
| `PostgreSQL tool 'pg_ctl' not found` | install PostgreSQL 14+, or set `PGBIN` to its `bin` folder, e.g. `set PGBIN=C:\Program Files\PostgreSQL\18\bin` |
| Port 15433, 8000 or 5173 already in use | another copy is running: `run.bat stop`; or set `STUDEASE_PG_PORT`; or stop the other program |
| `npm ci` fails with EPERM on Windows | a dev server is still holding files: `run.bat stop`, then run again |
| Login says "Wrong email or password" | the password is `DEMO_PASSWORD` from `backend/.env` (or the default); if you changed it after the first load, delete `.pgdata/loaded.flag` and run again |
| Want a clean slate | `run.bat stop`, delete the `.pgdata` folder, run `run.bat` |
| Page loads but every call fails | the API window shows the error; usually the database is not running: run `python scripts/dev.py db-up` |
