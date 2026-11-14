# Frontend

React 19, TypeScript, Vite, Tailwind 4, TanStack Query, React Router 7. No UI kit: the design system is one stylesheet
([frontend/src/index.css](../frontend/src/index.css)) and a small component file
([frontend/src/components/ui.tsx](../frontend/src/components/ui.tsx)). Every page below is built from them.

## Look and feel ("register paper")

The design vocabulary is an accounting register crossed with a poster: off-white paper, ink black, one orange, sand and
mint, a light serif for display type (Instrument Serif) over a neutral sans (Hanken Grotesk, self-hosted through npm),
1px ruled lines, and shapes with character.

| Element | Where | What it is |
|---|---|---|
| **Hero card** | first metric on a page | orange, one cut corner, diagonal stripes that drift with the mouse |
| **Stat card** | second metric | sand, a folder-tab notch in the top right |
| **Ink card** | third metric | black, the same tab (a warm grey in dark mode) |
| **Mint card** | fourth metric | light green, rounded |
| **Panel** | every table, form and chart | white sheet, 28 px radius, border darkens on hover, the title grows a wavy orange underline |
| **Pill button** | every action | 12 px radius; an orange fill slides in from the left on hover; presses down on click |
| **Stamp** | statuses | outlined capsule, tinted by meaning (green, amber, red, grey) |
| **Strike** | figures that do not agree | a hand-drawn orange line draws across the wrong number (the three-way balance on a student page) |
| **Line and donut charts** | overview, student page, scholarships, exceptions | lines draw themselves in, areas fade in, dots grow on hover and carry the entry as a tooltip; donuts draw slice by slice with an in-card explanation |
| **Wavy nav underline** | header links | an animated sine wave under the active link |

Colours are tokens (`--paper`, `--ink`, `--orange`, ...) defined for light, for dark, and for "dark by OS unless the user
chose light"; components never use literals, so both themes work everywhere. Dark mode follows the operating system and
can be toggled; the choice is remembered.

## Motion, and what never moves

- **Page load:** the header drops in, the title wipes up from a clip, metric cards rise in a stagger.
- **Scroll:** panels and tables slide up as they enter the viewport (`motion.ts`: one `IntersectionObserver`, classes
  added by script and removed after the reveal, so hover transforms and React re-renders never fight them).
- **Pointer:** hero stripes parallax with the mouse; cards lift on hover; table rows slide and show a dot.
- **Charts:** bars grow in, the donut draws its ring slice by slice, the trend bars rise.
- **Rule:** reveals use transform only, never opacity, so text is never semi-transparent over a background and nothing
  can stay invisible if an animation does not run.
- **Switches:** `?motion=off` turns motion off and remembers it (`?motion=on` restores it); `prefers-reduced-motion` is
  honoured; print styles remove all of it.

## Loading states

Nothing shows a blank page or a lone spinner.

| State | Treatment |
|---|---|
| App boot (before any code runs) | an inline splash in `index.html`: wordmark and a sliding bar |
| Session check | the splash component (breathing logo, sliding bar) |
| Any request in flight | a thin orange bar across the top of the window (appears after 120 ms so quick requests do not flicker) |
| A page loading data | **skeleton cards with the real shapes and labels** of the cards that replace them (cut corner, folder tab, mint), shimmering placeholders for the numbers, then a skeleton panel for the table |
| A button submitting | the button shows a spinner and disables itself |
| A list loading more | the "Load more" button shows a spinner |
| A write succeeding | a toast slides in at the bottom right (payment recorded, enrolled, exported, password changed) |
| A request failing | an error panel with the server's message, the request id to quote, and a "Try again" button |

## Pages by role

| Role | Pages |
|---|---|
| Not signed in | Sign in, Create account, Forgot password, Reset password |
| **Learner** | **Account** (balance cards, three-way reconciliation, pay now, enrollments with withdraw, invoices, ledger, state history, change password), **Enrol** (term, fee preview, scholarship checklist with reasons), **Scholarships** (awards and every decision), **Fees** (own program's schedule), invoice detail |
| Instructor | Students of the own program (no money), student enrolment status |
| Academic administrator | Overview, Students, Fee schedules, Scholarships, student pages with Withdraw |
| Support | the above (read) plus Exceptions with Resolve and Dismiss, and Record payment on a student page |
| Platform administrator | everything, plus Data quality |

## Exports

Every list and account has an Export group: **CSV**, **JSON** where the data is structured, and **Print / PDF** (the
browser's print dialog, with a print stylesheet that drops navigation, animation and card shapes).

- Lists that page (students, awards, exceptions) export **the whole filtered list**, not the visible page: the client
  follows the keyset cursor 200 rows at a time (`fetchAll`).
- CSV is UTF-8 with a byte-order mark so spreadsheet programs open rupee signs correctly, CRLF line ends, quoting per RFC
  4180, and **formula neutralisation**: a text cell starting with `=`, `+`, `-` or `@` that is not a number gets a leading
  apostrophe so a spreadsheet never runs it. Money columns are integer paise (named as such) so totals are exact.
- A learner can export their own ledger as a statement.

## Errors and pages that exist for the unhappy path

- **404** for unknown URLs, **403** for a page the role may not open, **500** for a render crash (React Router error
  boundary), each styled as a hero card with a way home.
- An expired or revoked session (any API 401) clears the session and returns to sign-in.
- nginx serves a static page ([frontend/public/50x.html](../frontend/public/50x.html)) when the API does not answer.
- Per-page `<title>` and `<meta name="description">` (a single-page app has one `index.html`, so each route sets its own);
  `index.html` carries a standalone default description, Open Graph tags, a theme colour for both schemes, a manifest and an
  SVG favicon. `robots.txt` keeps crawlers out of `/api/`.

## Accessibility

Skip link; visible focus ring (orange) on every control; labels on every input; status messages use `role="status"`,
errors `role="alert"`; the donut and bar charts carry text alternatives; the decorative progress bar is `aria-hidden` (its figures are on
the page); tables scroll horizontally on small screens; layout holds from 360 px upward.

## State and data access

TanStack Query caches responses for 30 seconds; writes invalidate exactly the keys they change (student, ledger, events,
overview). The API client ([lib/api.ts](../frontend/src/lib/api.ts)) is one fetch wrapper: bearer token from
`sessionStorage`, JSON in and out, the server's error envelope turned into a typed `ApiError`, and a handler that signs out
on 401. Payments send a fresh `Idempotency-Key` per submit.

## Data entry, accounts and invoices (added)

| Who | Screen | What |
|---|---|---|
| Academic admin, platform admin | Fee schedules | **Publish a new fee version** (closes the previous version the day before) |
| Academic admin, support, platform admin | Students | **Add student** (optionally with a learner sign-in); **Edit details** and **Enrol** on the student page |
| Academic admin, platform admin | Student page | **Assign a scholarship** (criteria still enforced) |
| Platform admin | Users | create staff and learner logins, enable or disable access |
| Learner | Account | edit name and housing; **Create a new account** is a button on the sign-in page |
| Everyone who sees invoices | Student page, invoice page | **Download** one invoice as CSV, or print it to PDF |

Who may do what is in [`permissions.md`](permissions.md) (generated from the route guards). The accent is orange (`--orange`), the app
icon and favicon are the hand-drawn cap, books and receipt (`public/logo.png`, `favicon.ico`, `apple-touch-icon.png`, `icon-192/512.png`).
Charts: the balance line is one point per ledger entry (red dot = charge, green dot = payment or award; above the zero line the student owes,
below it they hold credit); the "money by kind" donut sums ledger entries by kind.

## Loading performance

- **Route-level code splitting:** every page after sign-in is a `React.lazy` chunk (`App.tsx`), fetched the first time it is visited. A
  `Suspense` boundary in the shell shows the skeleton cards while the chunk loads. Sign-in, the error pages and the shell stay in the first
  bundle so the first screen paints at once. Shared libraries are split into `react` and `query` chunks that the browser caches across releases.
- **Cached forever, versioned by name:** hashed assets are served `immutable` by nginx, so a returning visitor downloads only what changed.
- **Lists are paged, not loaded whole:** keyset pagination, 50 rows then "Load more"; exports follow the cursor on demand.
- **Images:** the only raster image is the small logo, decoded asynchronously; charts are inline SVG (no chart library).
- **Fonts:** self-hosted variable fonts, latin subsets first.
