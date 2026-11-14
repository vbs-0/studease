# Testing

Run everything: `python scripts/dev.py test` (backend), `cd frontend && npm test`, `python scripts/dev.py lint`,
`cd frontend && npx tsc -b`, `python scripts/scrub_check.py`. CI runs the same set on every push.

## Strategy

The business rules are pure functions (`backend/app/domain/`), so most tests need no database and run in milliseconds.
Expected numbers in rule tests were worked out by hand from the specification (docs/architecture.md section 5) and
written next to the code, so a test failing means the code and the written rule disagree, not that two copies of the
same arithmetic drifted. Tests that need PostgreSQL are marked `db`, use a separate `studease_test` database that is
migrated to head, and skip with a clear message if the cluster is not running.

## Groups

| Folder | What it proves |
|---|---|
| `tests/test_ids_money.py`, `test_schema.py` | id formats, paise arithmetic and Indian digit grouping; every table and column is documented; enumerations match their `CHECK`s |
| `tests/domain/` | one file per rule family (fees, billing, scholarships, allocation, late fees, withdrawal and refunds, ledger, status) with boundary cases: equal amounts are allowed, one paisa over is flagged, ties break by priority |
| `tests/domain/test_purity.py` | the domain package imports no framework, database, clock or random source |
| `tests/datagen/` | exact volumes at both scales, determinism for a fixed seed, every anomaly injected exactly as labelled, the writers' output, validator behaviour on good and bad data, the reproducibility check |
| `tests/engine/test_migration.py` | the migrated database equals the Python schema exactly (no drift) |
| `tests/engine/` | detectors find every labelled case and nothing else, cannot see the ground truth (by signature), precision and recall maths, the COPY loader's constraints and rollback |
| `tests/api/test_security.py` | S-1 (no string-built SQL), S-3, S-4, S-6, S-7 (forged, expired, wrong-algorithm and disabled-user tokens), S-2 (learner and instructor scope), S-10, S-11, S-12, S-23, and a pinned "no throttling yet" test |
| `tests/api/test_reads.py` | paging without gaps or repeats, filters, the three-way reconciliation figures, invoice detail, overview totals, and a query-count budget (no N+1) |
| `tests/api/test_writes.py` | payment allocation and reconciliation, idempotent replay and mismatch, per-caller keys, two concurrent payments for one student, withdrawal and cancellation with reversals and refunds, exception resolution |
| `tests/api/test_learner.py` | sign-up (validation, duplicate email, no role or student smuggled in), enrolment (billing, scholarship decision, books reconcile three ways, ended or repeated term refused), self-service pay and withdraw, ownership checks, staff enrolment, own fees, change password |
| `tests/test_docs.py` | the generated documents are current and cover every table and field |
| `tests/test_scrub_check.py` | the public-repo hygiene scan catches each leak type, allows synthetic data, and the repository is clean |
| `frontend/src/lib/format.test.ts` | rupee formatting, dates, status tones |
| `frontend/src/lib/export.test.ts` | CSV quoting, line ends, formula neutralisation, empty cells |

## Properties worth knowing

- **Books always balance after a write.** Payment and withdrawal tests re-derive the balance three ways from the
  database after the write and require them to be equal.
- **The data checks classify rather than excuse.** The validator counts a violation as expected only when a ground-truth
  label explains it; anything else is "unexpected" and fails the run.
- **Concurrency is tested, not assumed.** Two simultaneous payments for one student must both succeed and must not allocate the same money twice.
- **Security tests assert behaviour, not configuration.** They forge tokens and call routes as the wrong role.

## What is not covered

- No browser end-to-end tests; the pages were exercised by hand against the running API.
- No load test beyond the full-scale data load (about 25 seconds for a million rows) and the query-count budget.
- Mail delivery is not exercised in tests (it needs a real mail server); its skip, redirect and no-raise paths are short but untested.

## Edge cases and validation

`backend/tests/api/test_edge_cases.py` holds the EC-xx tests: every field of every write endpoint at and beyond its bounds, hostile text,
malformed bodies and headers, idempotency conflicts, role sweeps. [`edge-cases.md`](edge-cases.md) lists each scenario, the expected
answer, what enforces it and the test that proves it. [`permissions.md`](permissions.md) is generated from the route guards and checked
for staleness by `tests/test_docs.py`.
