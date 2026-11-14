# StudEase: engineering practices

What we practise, where it lives in the code, why we chose it, and how far we took it. Each row is something
a reviewer can open and check. Rule ids (R-PAY-2, S-9) point to [`architecture.md`](architecture.md).

**Status:** written with the plan, before the code. The "Level" column states the intended depth. Measured
numbers (timings, row counts, test counts) are marked *target* until they are replaced with values copied
from `reports/` when the build is finished. Nothing here should be read as measured unless it says so.

How to read "Level":

| Level | Meaning |
|---|---|
| **Full** | Done to the standard we would ship to production |
| **Solid** | Correct and tested, with a known simpler shape than a large system would use; the upgrade is named |
| **Basic** | The minimum that is safe and honest; named as a limit |
| **Deferred** | Deliberately not built; the reason and the way to add it are written down |

---

## 1. Architecture

| Practice | Where | Why | Level |
|---|---|---|---|
| **Three-tier separation**: presentation, application, data in separate top-level folders | `frontend/`, `backend/`, `database/` | Each tier can be built, tested, deployed and replaced on its own; the brief's reviewers can find things | **Full** |
| **Pure domain layer** (functional core, imperative shell): rules are functions of their inputs with no database, HTTP, clock or randomness | `backend/app/domain/` | A money rule can be tested in microseconds with literal numbers, and cannot behave differently between generator, API and detector | **Full** |
| **Single source of truth for each rule**: generator, detectors and API all call the same function | `domain/*` imported by `datagen/simulate.py`, `engine/detect.py`, `api/payments.py` | Removes the classic bug where the test data and the product disagree about the rule | **Full** |
| **Schema as code with embedded data dictionary**: every column carries description, allowed values, unit and rule in `Column.info` | `backend/app/schema.py` | The migration, CSV column order, enum validation and `data_dictionary.md` are all derived from one file, so they cannot drift | **Full** |
| **One row shape end to end**: plain dicts keyed by column name | `Dataset` type used by generator, writer, validator, detectors, loader | No mapping layers to keep in step; the validator can run on files without a database | **Solid**: typed row classes would add editor help; not needed at 19 tables |
| **Dependency direction is one way**: `api` and `datagen` and `engine` depend on `domain`; `domain` depends on nothing | import structure, checked by a test that scans `domain/` imports | Keeps the rules portable and stops accidental coupling | **Full** |
| **Twelve-factor configuration**: every setting comes from the environment | `backend/app/config.py`, `.env.example` | Same build runs locally, in CI and on the server | **Full** |

## 2. Money correctness

| Practice | Where | Why | Level |
|---|---|---|---|
| **Integer minor units**: all amounts are `int` paise in `BIGINT` columns | every `*_paise` column; `money.py` | Binary floats cannot represent 0.10 exactly; sums of floats drift and reconciliation fails by a paisa | **Full** |
| **One rounding rule**: percentages in **basis points**, **round half up**, `(amount * bp + 5000) // 10000` | `money.pct` | Rounding is the usual source of one-paisa mismatches; one function means one behaviour | **Full** |
| **Credits are lines, not overwrites**: waivers, scholarships and adjustments are negative invoice lines pointing at the charge they reduce (`applies_to_line_id`) | `invoice_line` | The original charge stays visible; every reduction is explained by a row | **Full** |
| **Derived totals**: invoice total, outstanding, status and balance are computed from rows, never typed in | `domain/billing.py`, `domain/status.py`, `domain/ledger.py` | The brief requires derived values from source records; a stored total can be wrong, a computed one cannot disagree with its inputs | **Full** |
| **Append-only ledger** (double-check accounting): one signed `ledger_entry` per money movement | `ledger_entry`, `domain/ledger.py` | The balance is a sum that anyone can re-add; nothing is edited after the fact | **Solid**: single-sided signed ledger, not full double-entry with accounts; enough for one receivable per student |
| **Three-way reconciliation**: ledger sum = stated balance = invoices - payments + refunds | `datagen/validate.py` check 5, `engine/detect.py` | Three independent routes to one number; a bug in one route shows as a disagreement | **Full** |
| **Conservation checks**: allocations + unapplied remainder = payment; refund <= net paid | `domain/allocation.py`, `domain/withdrawal.py` and their tests | Money can neither appear nor vanish inside the system | **Full** |
| **De-allocation by reversal row**: a negative allocation instead of deleting the original | `payment_allocation` | Allocation history stays auditable after a withdrawal | **Full** |

## 3. Data modelling

| Practice | Where | Why | Level |
|---|---|---|---|
| **Primary key on every table, foreign key on every relationship** | `schema.py` | The brief's first acceptance test; lets the database reject orphans | **Full** |
| **Deterministic, human-readable identifiers** with zero padding and embedded parents (`ALLOC-PAY-2026-000001-01`) | `ids.py`, `ids.PATTERNS` | An id seen in a log or a CSV tells you what it is and where it belongs; format is validated by regex | **Full** |
| **Bridge table for many-to-many**: Payment N:M InvoiceLine | `payment_allocation` | One payment covers many lines and one line is paid by many payments | **Full** |
| **Effective dating** on prices (`effective_from`, `effective_to`) | `fee_schedule`; R-FEE-1 to R-FEE-3 | A price change must not rewrite past invoices; the invoice uses the version valid on its issue date | **Full** |
| **Database constraints as a second line of defence**: `CHECK` on enums, signs and date order; `UNIQUE` on natural keys | `schema.py` | A forbidden row is rejected even if the application has a bug (S-14) | **Full**, with one stated exception below |
| **A constraint deliberately left out**: no `UNIQUE (enrollment_id)` on `invoice` | `schema.py` comment | The brief requires a labelled duplicate-invoice anomaly to exist in the data; the validator and detector own that rule instead | **Solid**: a production system would add the constraint |
| **Event history**: every state change writes an `event` row with from-state and to-state | `event`, `domain/status.TRANSITIONS` | The brief says do not overwrite history; lifecycle validation replays these rows | **Full** |
| **Lifecycle as an explicit transition table** | `domain/status.py` | Illegal jumps (PAID back to ISSUED) are detectable by lookup, not by scattered `if`s | **Full** |
| **Ground truth isolated**: separate schema `gt` and separate folder | `gt.ground_truth`, `data/<scale>/ground_truth/` | Labels cannot leak into inputs by an accidental join; a test and a validation check enforce it | **Full** |
| **Normalisation**: third normal form for inputs; one denormalised snapshot (`student_balance`) kept on purpose | `schema.py` | The snapshot is the "stated" figure the reconciliation is meant to check | **Full** |

## 4. Synthetic data generation

| Practice | Where | Why | Level |
|---|---|---|---|
| **Simulation, not table filling**: the generator walks the 2026 calendar and calls the domain rules | `datagen/simulate.py` | Outcomes and labels come from documented rules, as the brief requires, and every row is consistent with every other | **Full** |
| **Fixed seed with named sub-streams**: `stream(seed, "payments")` | `datagen/rand.py` | Adding a random draw in one area does not shift the numbers in another, so changes stay local and reviewable | **Full** |
| **Exact volumes without random outcomes**: scholarships by "file applications until N awards", payments by "split instalments until N" | `datagen/simulate.py` | Hits 15,000 and 50,000 exactly while every decision is still made by a rule | **Full** |
| **One generator for both scales** | `generator.SCALES` | The starter set is a true miniature of the full set, not a separate script | **Full** |
| **Realistic distributions**: truncated-normal GPA, skewed program sizes, a behaviour mix for payments | `datagen/people.py`, `datagen/catalog.py` | Flat uniform data hides bugs that skew reveals, and reviewers score realism | **Solid**: distributions are reasoned, not fitted to a real institution's data (none is used) |
| **Valid baseline first, anomalies second** | `generator.generate` | Lets us prove the clean data has zero violations before adding the five cases | **Full** |
| **Isolated, labelled anomalies**: disjoint student sets; derived values not recomputed after injection | `datagen/anomalies.py` | Each case is cleanly attributable; the inconsistency is what the detector must find; unrelated rows are untouched | **Full** |
| **Byte-stable output**: rows sorted by primary key, fixed column order, `\n`, UTF-8 | `datagen/writer.py` | Makes checksums meaningful across machines and operating systems | **Full** |
| **Manifest with SHA-256 and row counts**; regenerate twice and compare | `manifest.json`, `datagen/repro.py` | Reproducibility is demonstrated, not asserted | **Full** |
| **No real personal data**: synthetic names, reserved `example.edu` domain | `datagen/people.py` | Lawful by construction; nothing to license or anonymise (S-21) | **Full** |

## 5. Validation, detection and evaluation

| Practice | Where | Why | Level |
|---|---|---|---|
| **Nine independent validation checks** on files, no database needed | `datagen/validate.py` | A reviewer can verify the dataset with Python alone | **Full** |
| **Violations classified as expected or unexpected** against ground truth | `validate.run` | The run passes only if every violation is one of the labelled cases | **Full** |
| **Detectors never see ground truth**: enforced by function signature | `engine/detect.run(ds)` | Otherwise the evaluation would measure nothing | **Full** |
| **Evaluation metrics**: precision, recall, F1 per issue type; reconciliation rate; collection rate | `engine/evaluate.py`, `reports/<scale>/evaluation.json` | The brief asks for measurable outputs; a detector that flags everything has recall 1 and precision near 0, so both are reported | **Full** |
| **Negative test of the validator itself**: corrupt one unlabelled row and expect failure | `tests/datagen/test_validate.py` | A check that can never fail proves nothing | **Full** |

## 6. API

| Practice | Where | Why | Level |
|---|---|---|---|
| **Versioned REST** under `/api/v1` with an **OpenAPI** contract | `main.py`, `/docs` | Clients can rely on the contract; the frontend types are generated from it | **Full** |
| **Uniform error envelope** with a machine code and a **request id** | `api/errors.py` | One shape for clients; one id to find the log line | **Full** |
| **Keyset pagination** (`after=<id>`), not offset | `api/deps.page` | Offset pagination reads and discards every skipped row; keyset uses the primary-key index and stays fast on the last page of 50,000 payments | **Full** |
| **Idempotent writes** with `Idempotency-Key`, scoped to the user and bound to a hash of the body | `api/payments.py`, `idempotency_key` | A retried request after a timeout must not record a second payment (S-9) | **Full** |
| **One transaction per write** with a **row lock** (`SELECT ... FOR UPDATE`) on the student | `api/payments.py`, `api/enrollments.py` | Two concurrent payments cannot both allocate the same outstanding amount (S-15) | **Full** |
| **Side effects after commit**: mail is sent from a background task once the transaction is durable | `api/payments.py` | A mail failure cannot roll back a payment, and no mail is sent for a payment that did not commit | **Solid**: an outbox table with a worker would survive a crash between commit and send |
| **Strict input models**: unknown fields rejected, ranges and id patterns enforced | Pydantic models with `extra="forbid"` | Bad input stops at the boundary (S-10) | **Full** |
| **Health and readiness endpoints** | `/healthz`, `/readyz` | The deploy script waits on readiness and rolls back if it never comes | **Full** |

## 7. Security

The full list is section 12 of the specification. Summary:

| Practice | Where | Why | Level |
|---|---|---|---|
| **Bound parameters only**, plus a test that scans for string-built SQL | `api/*.py`, `tests/api/test_security.py` | SQL injection (S-1) | **Full** |
| **Object-level authorisation** from token claims, never from the URL | `api/deps.py` | A learner cannot read another student by changing an id (S-2) | **Full** |
| **scrypt** password hashing, constant-time compare | `security.py` | Slow, salted, memory-hard (S-3) | **Full** |
| **JWT** with pinned algorithm and short expiry; **startup guard** on weak secrets | `security.py`, `config.Settings.check` | Prevents `alg=none` and forgotten default secrets (S-6, S-7) | **Solid**: token lives in `localStorage`; httpOnly cookie plus CSRF token is the upgrade |
| **Single-use reset link** bound to the password hash; uniform response | `api/auth.py` | A used or leaked-then-used link stops working; no account enumeration through reset (S-23) | **Full** |
| **Mail hygiene**: STARTTLS, credentials only on the server, never to synthetic addresses, bodies never logged | `mail.py` | S-22 | **Full** |
| **Least privilege**: dedicated database role, localhost-only database and API, non-root hardened service | `deploy/` | Limits what a compromise can reach (S-13, S-17) | **Full** |
| **Security headers and HTTPS** | `deploy/nginx-studease.conf` | Clickjacking, sniffing, downgrade (S-16) | **Full** |
| **Repository scrub check** before any push and in CI | `scripts/scrub_check.py` | A public repo must not carry emails, addresses, hosts or secrets (S-20) | **Full** |
| **Public demo accepts writes** | owner decision (S-8) | Reviewers can exercise the whole workflow; data is synthetic and restorable | **Accepted risk** |
| **Login throttling and timing equalisation** | not built (S-5) | Lockouts obstruct manual testing during the build | **Deferred**: design is written in the spec |

## 8. Performance and optimisation

| Practice | Where | Why | Level |
|---|---|---|---|
| **Bulk load with `COPY`**, one transaction, parent-first order | `engine/loader.py` | Row-by-row `INSERT` of about a million rows takes minutes; `COPY` takes seconds | **Full**. *Target:* full dataset loaded in under 60 s on the 1 GB server |
| **Indexes on every foreign key the API filters by**, composite where the query sorts | `schema.py` | Without them each ledger page is a table scan | **Full** |
| **No N+1 queries**: each endpoint issues a fixed number of statements; children are fetched with `= ANY(:ids)` | `api/students.py`, `api/invoices.py` | Query count must not grow with page size | **Full**, asserted by a statement-count test on two endpoints |
| **Generator in linear time**: lookups by dict, no repeated scans | `datagen/simulate.py` | The full scale must be regenerable while a reviewer waits | **Solid**. *Target:* full scale in under 60 s on a laptop; pure Python, no vectorisation |
| **Connection pool** with pre-ping, sized for a 1 GB server | `db.py` (pool 5 + 5 overflow) | Reuses connections; survives a database restart | **Full** |
| **Response compression** and **long-lived caching of hashed assets**, no caching of `index.html` | `deploy/nginx-studease.conf` | Faster repeat visits without stale deployments | **Full** |
| **Route-level code splitting** and client caching with stale-while-revalidate | `frontend/src/App.tsx` (lazy routes), TanStack Query | The first page does not download every page | **Solid**: no service worker or prefetching |
| **Aggregates computed in SQL**, not in Python | `api/metrics.py` | The database sums 50,000 payments faster than transferring them | **Solid**: computed per request; a materialised view is the upgrade if the data grows 10x |

What we did not optimise, on purpose: no caching layer (Redis), no read replicas, no async database
driver, no table partitioning. At about one million rows on one server none of them would be measurable,
and each adds a failure mode.

## 9. Testing

| Practice | Where | Why | Level |
|---|---|---|---|
| **Test-first for every rule**: the test with literal numbers is written before the function | `tests/domain/` | The expected number is decided from the rule, not copied from the code's output | **Full** |
| **Boundary values**: GPA 8.99 and 9.00; term day 14, 15, 30, 31; late-fee floor and cap; effective date on the exact day | `tests/domain/` | Off-by-one errors live at the edges | **Full** |
| **Property-style conservation tests** over a table of cases | `tests/domain/test_allocation.py` | States an invariant, not just an example | **Solid**: hand-picked table, not a property-testing library |
| **Test pyramid**: many pure unit tests, fewer generator tests, fewest API tests on a real database | `tests/domain`, `tests/datagen`, `tests/engine`, `tests/api` | Fast feedback where the logic is; real Postgres where constraints and locks matter | **Full** |
| **Real database in API tests**, not a mock | `tests/api/conftest.py` | Mocks would not catch a wrong constraint, a missing index or a lock bug | **Full** |
| **Concurrency test** for double allocation | `tests/api/test_writes.py` | The row lock is only proven by trying to break it | **Solid**: 20 racing pairs, not a model checker |
| **Decision-pinning tests**: a test asserts that a deferred feature is absent | `tests/api/test_security.py` (S-5) | Makes a deliberate omission visible and stops it changing by accident | **Full** |
| **Continuous integration** on every push | `.github/workflows/ci.yml` | Lint, tests, generate, validate, reproducibility, frontend build | **Full** |

## 10. Frontend

| Practice | Where | Why | Level |
|---|---|---|---|
| **No business rules in the browser**: it formats and displays | `frontend/src/` | A rule in two languages is two rules | **Full** |
| **Types generated from the API contract** | `frontend/src/lib/types.ts` | A backend field rename fails the frontend build instead of failing in production | **Full** |
| **Design tokens** as CSS custom properties, light and dark themes | `frontend/src/index.css` | One place to change a colour; themes without duplicate styles | **Full** |
| **Motion with an off switch**: honours `prefers-reduced-motion`, and `?motion=off` | `frontend/src/lib/motion.ts` | Animation must never block reading or cause discomfort | **Full** |
| **Accessible basics**: semantic tables, labelled inputs, visible focus, sufficient contrast | components | The console is mostly tables of money; screen readers need real table markup | **Solid**: checked by hand and by lint rules, not by an audited screen-reader pass |
| **Loading, empty and error states** on every page | pages | A blank screen is not an answer | **Full** |
| **Responsive from 360px** | pages | Learners check balances on phones | **Solid** |

## 11. Delivery and operations

| Practice | Where | Why | Level |
|---|---|---|---|
| **Locked dependencies**, frozen installs | `uv.lock`, `package-lock.json` | The same versions everywhere (S-19) | **Full** |
| **Migrations** for every schema change | `database/migrations/` | The database is rebuilt the same way on every machine | **Full** |
| **One-command tasks** | `Makefile` | A reviewer types `make all`, not a paragraph | **Full** |
| **Deploy with automatic rollback** on failed readiness | `deploy/deploy.sh` | A bad release does not stay up | **Solid**: one server, brief restart; blue-green is the upgrade |
| **Structured JSON logs** with request ids | `backend/app/logging.py` | Logs can be filtered and joined to an error a user reports | **Solid**: no central log store or metrics dashboard |
| **Small, meaningful commits** | git history | The guidelines ask that the evolution of the work be understandable | **Full** |

## 12. Documentation

| Practice | Where | Why | Level |
|---|---|---|---|
| **Specification with numbered rules** | `docs/architecture.md` | A test, a line of code and a sentence can cite the same id | **Full** |
| **Decision records**: choice, alternatives, reason, cost | `docs/decisions.md` | Answers "why this and not that" | **Full** |
| **Worked example with real numbers** | `docs/walkthrough.md` | One student followed end to end is easier to check than any diagram | **Full** |
| **Generated reference docs** with a freshness test | `docs/data_dictionary.md`, `docs/erd.md` | Generated docs cannot go stale | **Full** |
| **Honest limits and AI disclosure** | `README.md`, `prompts/AI_USE.md` | The guidelines ask for both | **Full** |

## 13. Deliberately not done

| Not done | Why | When to add |
|---|---|---|
| Login throttling, timing equalisation | Owner's decision during testing | Before real users |
| Read-only demo mode | Owner's decision: reviewers should be able to write | If the public demo is abused |
| Bounced or reversed payments | Not in the brief; adds a state machine | When a payment gateway is connected |
| Recurring monthly late fee | One fee per invoice keeps the rule checkable by hand | If policy requires it |
| Multi-currency, multi-institution | Not in the brief | When a second institution joins |
| Message queue, cache, replicas | Not measurable at this size | At roughly 10x the data or concurrent staff use |
| Mobile app | Not in the brief | On request |
