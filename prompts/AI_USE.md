# How AI was used

The brief allows AI assistance and asks candidates to explain it. This is the plain account.

## What the assistant did

- Drafted the specification, the plan and the documents from my instructions and decisions.
- Wrote most of the code and tests: the schema, the pure rule functions, the generator, the validator and detectors,
  the loader, the API, the React pages, the deployment files and the CI workflow.
- Ran the tests, the generator and the application, read the failures and fixed them.

## What I decided

- The product shape: a full three-tier application, not only a dataset, with the stack and the folder layout.
- The rules: integer paise, round half up; credits as negative lines; oldest-due-first allocation; the late-fee formula;
  the refund cap; the three-way balance identity. These are written in `docs/architecture.md` section 5 with reasons.
- The scope calls: public demo logins can write; login throttling deferred while testing; instructors see no money.
- What counted as done: exact volumes at both scales, zero unexpected validation violations, byte-identical regeneration.

## How I checked the output

- Rule tests use numbers worked out by hand from the written rule, so a passing test means the code matches the rule.
- The generator was run twice and compared by checksum; the full-scale run was loaded into PostgreSQL.
- The worked example in `docs/walkthrough.md` (one student, every record) was recomputed by hand.
- Security claims are tests that forge tokens and call routes as the wrong role, not statements in a document.
- The application was run locally and exercised in a browser.

## Where the assistant was wrong or I had to correct it

- A first test run hung because a database process kept a pipe open; fixed by starting the cluster detached.
- An entity-type column was too short for one label; the database tests caught it before any data was lost.
- A security test caught the assistant building SQL with string formatting (constants only, but it broke the rule); rewritten with literal queries.
- A claim in `docs/practices.md` that every rule was written test-first was inaccurate; it now says what was actually done.
- Several figures in documents were generated from the data rather than typed, because typed numbers drifted.

## Limits I want to be upfront about

- The detection score of 1.0 is by construction (see the README), not evidence of generalisation.
- The assistant's replies are not reproduced here; `PROMPTS.md` lists my instructions, and the repository history shows the work in meaningful commits.
- I can explain any file, rule or decision in the walkthrough.
