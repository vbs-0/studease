# Prompt history

Every instruction I gave the AI assistant (Claude, in the Claude Code desktop app) while building this repository, in order.
My messages are verbatim, spelling and all. Replies are summarised, not quoted; the code and documents they produced
are the repository itself. Where I referred to my own earlier project by name I have written "an earlier project";
I will explain it in person. Anything that identifies a server or an account has been replaced by a placeholder in angle brackets.

## Session 1: understanding the brief and choosing the stack

**P1** (with the full hackathon brief pasted after it)
> wake up wake up hackathon round
> ... [the brief: tuition and fees, scholarship eligibility and payments, student-balance reconciliation, 11 entities, volumes, five anomalies, validation, exports, reproducibility]
> read it and get ready and we are allowed to use ai

*Result:* the assistant restated the problem and asked nothing; I decided to build a full application, not only the dataset.

**P2** (with a folder of my earlier project's front end attached as reference)
> for ur referance this is our previus project remember animations and design etc.. deploymet thing etc...

*Result:* the assistant read the earlier project's design system and deployment pattern so this project could look and ship the same way.

**P3**
> nah first tell tech stack whcih will be usefull etc...

*Result:* a stack recommendation. I chose React + TypeScript, FastAPI, PostgreSQL, with uv, Alembic, pytest and Vite.

**P4** (with a domain registration form pasted)
> help me to config this '...'

*Result:* the assistant told me which fields to fill. **P5:** `done got domain` (a screenshot of the active domain).

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
> and also plan for project end to end  etc..

**P8**
> remember they told to maintain frontend backend etc.. as seperate folders as 3 tire architecture

**P9**
> use the best practices possible the best optimised work nto just a prototype

**P10** (sent while the assistant was writing the specification)
> make sure to include the document for each and everything don't miss a single thing including logics etc.. all and all and all
> next round will be based on current code and whats on it why this that etc... so dont miss a single point to document and guide of how to run setup etc... all and all in a one or few docs netely designed arranged

*Result of P6 to P10:* `docs/architecture.md` (the specification, with numbered rules), `docs/plans/` (a 13-task plan),
and a first `docs/practices.md`.

**P11** (a security review command, with this argument)
> check plans are secure or not

*Result:* the review tool could not run (no git repository at that point), so the assistant reviewed the plan by hand; it
found gaps (idempotency scoping, token rules, reset links, headers, secrets hygiene) that became controls S-1 to S-23.

**P12**
> edit and fix the plan i need it to be end to end perfect and document a proctice.md showing whatever the practices we used where why for how much level of optimisation etc... and highilight every technatlity on it

**P13**
> keeping this 'Public demo logins can write...' publicaly is not an issue
> for now not implement this coz we are testing it 'Login limit is per email only...'
> also grab smtp from an earlier project which is hosted on same server and use it

*Decisions recorded:* the demo accepts writes (S-8); throttling and timing equalisation are deferred (and pinned by a test).

**P14**
> dont mentone <the earlier project> anywhere on any docs including prompt history doc we are taking refreance form it i can say it manually

*Result:* the project name was removed everywhere and `scripts/scrub_check.py` now fails the build if it reappears.

## Session 3: building

**P15** (an execution skill was invoked with this text)
> tell whatever i need to bring from outside now
> and yah u can start building it inline

**P16**
> remember we need to run it locally aswelll

*Result of P15 and P16:* the assistant built, test by test: the schema and migrations; the pure domain rules (fees, billing,
scholarships, allocation, late fees, withdrawal, ledger, status); the generator with named random streams; the five anomaly
injectors and ground truth; the writers, validator, reproducibility check and detectors; the loader; the generated documents.
Each step ended with the test suite and a commit.

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
> have u using .env ?
>
> build implement everything quickly and run let me see

*Result of P17 and P18:* the FastAPI application and its 60+ API and security tests; the React application; custom 404, 403
and crash pages; a static 50x page; per-route titles and meta descriptions; a favicon and manifest; the `.env` mechanism
(already used, now documented); the deployment files and CI; this documentation. I ran the application locally and checked
sign-in, the overview, the student page and the 404 page in a browser.

## Session 5: deploying and redesigning

**P19**
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
> deploy to server first
> dont push to git till i told u to

*Result:* the application was deployed to the server (nginx, systemd service, database role, TLS certificate, the five demo
logins); the front end was redesigned from the earlier project's design language (cut-corner and folder-tab cards, wavy nav,
ticker, pill buttons, skeleton cards with real shapes, top progress bar, splash, toasts, charts that draw in); CSV, JSON and
print exports were added to every list and account; learners gained sign-up, enrolment with a fee preview and scholarship
checklist, self-service payment and withdrawal, their own awards, fees and statement, and a change-password form; staff can
enrol a student. Nothing was pushed to the repository, as instructed.

## Other tools

No other AI tool was used. No prompts were sent to anything other than the assistant above.
