# Database tier

PostgreSQL 14 or newer. The schema is defined once, in Python (`backend/app/schema.py`), and everything else is derived
from it: the Alembic migration in `migrations/versions/`, the data dictionary and ERD in `docs/`, the CSV headers and the
bulk loader. A test fails if the committed migration no longer matches the schema.

| Path | What |
|---|---|
| `alembic.ini`, `migrations/` | schema as migrations (`python scripts/dev.py migrate`) |
| `seed/starter.sql` | the starter dataset as plain SQL inserts, for anyone who wants it without Python |
| `seed/starter_ground_truth.sql` | the labelled anomalies, loaded into their own `gt` schema |

## What the database enforces itself

Primary keys, foreign keys, unique keys, `NOT NULL`, and a `CHECK` for every enumeration, sign and range rule, for
example: a credit line must be negative, a learner login must name a student, an award must be positive. The
backend validates first, but a bug cannot write a forbidden row because the database refuses it (tested in
`backend/tests/engine/test_loader.py`).

Ground truth lives in the separate `gt` schema and is never referenced by a foreign key or read by application code
except the evaluation run.

## Local development cluster

`python scripts/dev.py db-up` creates and starts a throwaway cluster in `.pgdata/` on `127.0.0.1:15433` with roles and
databases `studease` and `studease_test`. It never touches another PostgreSQL on the machine. `db-down` stops it,
`db-reset` recreates it.

## Loading data

```bash
python scripts/dev.py load                  # starter data (default)
SCALE=full python scripts/dev.py load       # 10,000 students; about 30 seconds with COPY
```

The loader truncates every table and bulk-loads parents first inside one transaction, so a failed load leaves the
previous data in place. It then seeds one demo login per role. Production database creation and permissions are in
[docs/deploy.md](../docs/deploy.md).
