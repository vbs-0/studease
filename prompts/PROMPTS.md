# Prompt history

Every instruction I gave the AI assistant (Claude, in the Claude Code desktop app, and chatgpt and qwen, deepseak aswell) while building this repository, in order.
My messages are verbatim, spelling and all. Replies are summarised, not quoted; the code and documents they produced
are the repository itself. Where I referred to my own earlier project by name I have written "an earlier project";
I will explain it in person. Anything that identifies a server or an account has been replaced by a placeholder in angle brackets.

## Session 1: understanding the brief and choosing the stack

**P1** (with the full hackathon brief pasted after it)
> wake up wake up hackathon round
> ... [the brief: tuition and fees, scholarship eligibility and payments, student-balance reconciliation, 11 entities, volumes, five anomalies, validation, exports, reproducibility]
> read it and get ready and we are allowed to use ai

*Result:* The assistant restated the problem and asked nothing; I decided to build a full application, not only the dataset.

**P2** (with a folder of my earlier project's front end attached as reference)
> for ur referance use this document for desing and animations and UI/UX remember animations and design etc.. deploymet thing etc...

*Result:* The assistant read the earlier project's design system and deployment pattern so this project could look and ship the same way.

**P3**
> nah first tell tech stack whcih will be usefull etc...

*Result:* A stack recommendation. I chose React + TypeScript, FastAPI, and PostgreSQL, with `uv`, `Alembic`, `pytest`, and `Vite`.

**P4** (with a domain registration form pasted)
> help me to config this '...'

*Result:* The assistant told me which fields to fill. 

**P5** (a screenshot of the active domain)
> done got domain

## Session 2: architecture and plan

**P6**
> first lets create an a robust 3-tire architecture seprately / backend fastapi / postres and frontend same as an earlier project

**P7** (a planning skill was invoked with this text)
> first build a robust architecture make sure everything is considered including test files create a folder and architecture and plan end to end of the project including the design etc...
> implement on this folder and save everything on this folder make sure u not missed anything or mis alligned and maintain perfect folder structure
> <local workspace folder>
> we have server i can handle linux server or u can simply use
> ssh <alias> will connect to it
> first create architecture and end to logics perfectly
> and also plan for project end to end etc..

**P8**
> remember they told to maintain frontend backend etc.. as seperate folders as 3 tire architecture

**P9**
> use the best practices possible the best optimised work nto just a prototype

**P10** (sent while the assistant was writing the specification)
> make sure to include the document for each and everything don't miss a single thing including logics etc.. all and all and all
> next round will be based on current code and whats on it why this that etc... so dont miss a single point to document and guide of how to run setup etc... all and all in a one or few docs netely designed arranged

*Result of P6 to P10:* `docs/architecture.md` (the specification, with numbered rules), `docs/plans/` (a 13-task plan), and a first draft of `docs/practices.md`.

**P11** (a security review command, with this argument)
> check plans are secure or not

*Result:* The review tool could not run (no git repository at that point), so the assistant reviewed the plan by hand; it found gaps (idempotency scoping, token rules, reset links, headers, secrets hygiene) that became controls S-1 to S-23.

**P12**
> edit and fix the plan i need it to be end to end perfect and document a proctice.md showing whatever the practices we used where why for how much level of optimisation etc... and highilight every technatlity on it

**P13**
> keeping this 'Public demo logins can write...' publicaly is not an issue
> for now not implement this coz we are testing it 'Login limit is per email only...'
> also grab smtp from an earlier project which is hosted on same server and use it

*Decisions recorded:* The demo accepts writes (S-8); throttling and timing equalisation are deferred (and pinned by a test).

**P14**
> dont mentone <the earlier project> anywhere on any docs including prompt history doc we are taking refreance form it i can say it manually

*Result:* The project name was removed everywhere, and `scripts/scrub_check.py` now fails the build if it reappears.

## Session 3: building

**P15** (an execution skill was invoked with this text)
> tell whatever i need to bring from outside now
> and yah u can start building it inline

**P16**
> remember we need to run it locally aswelll

*Result of P15 and P16:* The assistant built, test by test: the schema and migrations; the pure domain rules (fees, billing, scholarships, allocation, late fees, withdrawal, ledger, status); the generator with named random streams; the five anomaly injectors and ground truth; the writers, validator, reproducibility check, and detectors; the loader; and the generated documents. Each step ended with the test suite and a commit.

## Session 4: API, front end, polish

**P17** (answering "start on the API?")
> Yes, build API

**P18** (sent while the API was being written)
> OK to copy the SMTP settings for locall aswell not an issue this is hackathon we need to win
>
> have u also included error pages etc... aswelll
>
> Add a custom 404 etc.. pages
>
> it still feel like actuall professional thing coz still many importent things are missing na
>
> Add meta descriptions
>
> mentone it on doc and read me
>
> whatever these litttle extra things we doing like deploying etc... everything should be documented
>
> Add a favicon
>
>
> build implement everything quickly and run let me see

*Result of P17 and P18:* The FastAPI application and its 60+ API and security tests; the React application; custom 404, 403, and crash pages; a static 50x page; per-route titles and meta descriptions; a favicon and manifest; the `.env` mechanism (already used, now documented); the deployment files and CI; and this documentation. I ran the application locally and checked sign-in, the overview, the student page, and the 404 page in a browser.

**P19**
> doine i got domain done setting up dns and everything on server let me finish the req and seup lets deploy to the server

## Session 5: deploying and redesigning

**P20**
> I'll paste the URL <the new public repository>
>
> and also
>
> first redesign the ui animations bruh not even close to the earlier project bruuh
>
> shapes structure animations feel structure
>
> and no proper loading animations etc.. aswell na bruh
>
> and and need export options
>
> also why lerner jhave only few options
>
> and also no create etc... options ?? for learner etc... and no create acc or signup etc... ?
>
> let me deploy to server first

*Result of P19 and P20:*
- **Deployment:** Deployed to the server (`nginx`, `systemd` service, database role, TLS certificate, and the five demo logins). Nothing was pushed to the public repository, as instructed.
- **UI Redesign:** Rebuilt the front end using the earlier project's design language (cut-corner and folder-tab cards, wavy nav, ticker, pill buttons, skeleton cards with real shapes, top progress bar, splash screen, toasts, and animated charts).
- **Features & Exports:** Added CSV, JSON, and print exports to every list and account; learners gained sign-up, enrolment with a fee preview and scholarship checklist, self-service payment and withdrawal, personal awards/fees/statements, and a change-password form; staff gained student enrolment.

**P21**
> who can change fee schedule add students enter data etc... / assign scholarship / still why there is no create etc.. acc / also invoice
> etc... available na ? so where is download option ? / did u cover all Edge Cases / Negative Scenarios end to end? documented and listed
> on an edge-case.md document? / learner and others also need some graphs pie and line graphs with nice colors and animations / remove this
> bottom bar / is it possible to use some diff good color instead of orange / also i need permission matrix document as well

*Result:*
- **Admin & Staff Workflows:** Removed the bottom ticker; added staff screens and endpoints for fee versions, adding students, editing profiles, assigning scholarships, and managing users, plus downloadable invoices.
- **Charts & Documentation:** Added line and donut charts to the overview, student, scholarship, and exception pages; auto-generated `docs/permissions.md` from route guards; created `docs/edge-cases.md` and `tests/api/test_edge_cases.py` to list and verify negative scenarios.

**P22**
> make sure all validations are covered / here use this as favicons and icons

*Result:* Every write endpoint's field bounds were tested (`EC-01` to `EC-35`), which caught and fixed a real defect (a NUL character in text previously caused a `500` error, now returns `422`); the supplied artwork became the favicon, app icons, and in-app logo.

**P23**
> nah change back to last orange colour pls

*Result:* The accent returned to orange, and chart colours were re-based on it.

**P24**
> whats the use of it when u only showing one thing on chart / what this chart says, ups and downs means what? what is points and numbers

*Result:* The donut chart now shows ledger money broken down by kind (multiple slices), and both charts carry a plain-language explanation, a zero line labelled "settled", coloured dots (red for charges, green for payments), and tooltips naming each entry; the line chart no longer smooths over missing values.

## Other tools

No other AI tool was used. No prompts were sent to anything other than the assistant above.
