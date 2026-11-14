# Decisions

The choices that could reasonably have gone another way, each with the reason and the cost. Rule-level decisions
(rounding, credit lines, allocation order, late-fee formula) are in [architecture.md](architecture.md) section 5 next
to the rule they affect; this page covers the engineering ones.

| # | Decision | Why | Cost or alternative |
|---|---|---|---|
| D-1 | **Three folders, three tiers** (`frontend/`, `backend/`, `database/`) | The brief asks for separation; each tier has its own tests and can be run or deployed alone | A little duplication (enumerations appear in the schema, the API models and the UI) |
| D-2 | **Pure `domain/` package** with no framework, clock, random source or database | Every rule is testable with plain dicts in milliseconds; a test enforces the boundary | Routers must load rows and pass them in; the write endpoints are longer than a "fat model" would be |
| D-3 | **Integer paise and basis points**, round half up, one helper | Floats cannot represent money; one rounding rule means two code paths cannot disagree by a paisa | Everything is formatted at the edge; the data looks large (`100000` is one thousand rupees) |
| D-4 | **Credits are negative lines pointing at the charge** (`applies_to_line_id`) | A waiver, a scholarship and a withdrawal adjustment all reduce a specific fee and keep the history of why | Outstanding per line needs a join; solved with one pass over the lines |
| D-5 | **Append-only ledger and events; reversals are negative rows** | Nothing is overwritten, so any balance can be replayed and audited | Current-status columns are a cache of the history; both are written in one transaction |
| D-6 | **Three-way balance reconciliation** (stated = ledger = invoices - payments + refunds) | Two independent routes to the same number catch a fault in either path | Three queries per student view |
| D-7 | **SQLAlchemy Core, not the ORM** | The queries are the design; plain SQL with bound parameters is easier to read, review and test than relationship graphs | More SQL text; no automatic unit of work (the write endpoints manage the transaction explicitly) |
| D-8 | **The schema is Python (single source of truth)** | Alembic migrations, the data dictionary, the ERD, the CSV headers and the loader all derive from it, so they cannot drift; a test fails if a document is stale | The migration is regenerated from the schema while the project is young, not hand-written per change |
| D-9 | **One advisory lock plus a student row lock for writes** | Ids are `max + 1`, so id allocation must be serialised; the row lock stops two payments for one student allocating the same debt | Writes are strictly sequential. Upgrade path: database sequences for ids, keep the row lock |
| D-10 | **Idempotency key stored per caller with a hash of the body** | A retried payment returns the first answer; the same key with different content is an error, not a silent second payment | One table and a lookup under the lock |
| D-11 | **Detectors recompute the rules and never receive the ground truth** (enforced by their signatures) | Keeps detection honest: the score cannot come from reading the answers | Detectors share the rules with the generator, so a perfect score is expected; documented in the README |
| D-12 | **Validator classifies violations as explained or unexpected** | Injected anomalies must break the rules in exactly the labelled places; anything else is a generator bug | More bookkeeping than a pass/fail count |
| D-13 | **One generator parameterised by scale** | The starter set and the full set cannot diverge in behaviour; a fast set is used for tests | The starter set is a sample, so some rates differ slightly from the full set |
| D-14 | **Reproducibility by named random streams and byte-stable output** | Adding a feature that draws numbers does not change everything else; checksums are over uncompressed CSV with `\n` line endings (`.gitattributes` enforces them on Windows) | Streams must be named and kept stable |
| D-15 | **Frozen "as of" date (2026-09-05)** | A reproducible dataset needs a fixed present; every status and balance is derived as of that day | No scheduler; new writes are dated the as-of day |
| D-16 | **JWT in `sessionStorage`, bearer header, no cookies** | No CSRF surface, no credentials mode in CORS; the token dies with the tab | Reachable by script on the page, so the CSP is strict and the app loads no third-party scripts |
| D-17 | **Role and enabled flag read from the database on every request** | Disabling a user or changing a role takes effect at once, whatever an old token claims | One indexed lookup per request |
| D-18 | **Out-of-scope objects answer 404, not 403** | An id cannot be probed to learn whether it exists | A legitimate user cannot tell "missing" from "not yours" |
| D-19 | **Instructors see no money** | The brief says instructors see enrollment and hold status, not payments | The overview and ledger routes are closed to that role; the spec's "staff" table was narrowed to match |
| D-20 | **Login throttling and timing equalisation deferred** | Owner decision while the system is under hand testing; lockouts get in the way | A guessing attack is not slowed. A test pins the absence; the design for adding it is in architecture section 12 |
| D-21 | **Public demo accepts writes** | Reviewers can exercise the whole workflow | Anyone can change demo data; all data is synthetic and `load` restores it |
| D-22 | **Cross-platform runner in standard-library Python** (`scripts/dev.py`), Makefile forwards to it | The author works on Windows; reviewers may use Linux or macOS; no extra tool to install | Slightly more code than a Makefile alone |
| D-23 | **Local PostgreSQL cluster created under `.pgdata`** on a non-default port with trust auth, localhost only | Tests and the app never touch a database the developer already has | Trust auth is for development only; the production runbook uses a password and a restricted role |
| D-24 | **Hand-written API client, no code generation** | The surface is small; one 60-line wrapper is easier to review than a generated one | Response shapes are not type-checked on the frontend (they are typed loosely where read) |
| D-25 | **Per-route titles and meta descriptions set in the client** | One `index.html` serves every route; each page sets its own title and description for sharing and accessibility | Crawlers that do not run JavaScript see only the default description, which is written to stand alone |
| D-26 | **Currency INR in paise** | The brief names no currency; the examples read as Indian higher education | Assumption recorded in architecture section 11 |

## Things deliberately not built

Refund payout workflow beyond "approved" (no endpoint marks a refund paid), invoice cancellation by itself (only through
withdrawal), editing fee schedules, user management screens, multi-currency, and a scheduler for invoicing and late fees.
Each would be a straightforward addition on the same structure; none is needed to demonstrate the rules.

## Added with the learner features and the redesign

| # | Decision | Why | Cost or alternative |
|---|---|---|---|
| D-27 | **Self-service sign-up creates a synthetic student** | A learner needs an account to enrol, pay and see awards; the brief's data are synthetic, so a new student is one more synthetic row | Public and unthrottled while throttling is deferred; the form warns to use throwaway details |
| D-28 | **One enrolment function for learners and staff** | The billing and scholarship rules run in exactly one place; a staff enrolment cannot differ from a self-service one | The function is long; it is the only multi-table create |
| D-29 | **New rows are dated by the term calendar** | The generated data obey rules such as `enrolled_on <= term start`; dating a late sign-up "today" would break them | A new learner appears to have enrolled on the first day of term |
| D-30 | **Payment and withdrawal are shared functions behind two routes** | The learner route differs only in where the student comes from (the token) and in the allowed payment methods | Two thin route functions per action |
| D-31 | **Exports run in the browser** | The data is already authorised and in memory; no new server surface, no file storage, same permissions as the page | A very large export is bounded by `fetchAll`'s cap (20,000 rows) and the browser's memory |
| D-32 | **CSV neutralises formulas** | A name or note such as `=HYPERLINK(...)` would execute when the file is opened in a spreadsheet | A leading apostrophe appears in such cells |
| D-33 | **Reveals use transform, never opacity** | Text is never semi-transparent over a coloured card, and content cannot stay hidden if an animation does not run | Less soft than a fade |
| D-34 | **One stylesheet and one component file for the design system** | Every page uses the same shapes; a restyle is one place | `index.css` is long; it is organised by section with comments |
| D-35 | **API port 8110 on the server** | The default port was taken by another service on the same machine | Documented in `docs/deploy.md` and the unit and nginx files |
