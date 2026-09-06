# Verification Report — Gullak V2 (+ Group Expense Split & UPI Settlement)

All items below were actually run in this build environment against this exact codebase (not assumed).

## 1. Automated tests

```
python manage.py test
```

**Result: 143/143 tests passing** (up from 123 before this update), run against a fresh SQLite test database, confirmed on the final run immediately before packaging. Zero existing tests were modified or removed in this round — the 20 new tests are entirely additive, in a new `expenses/tests.py`.

New in this round (`expenses` app, 20 tests):

| Test class | What's covered |
|---|---|
| `LogExpenseServiceTests` | Equal split divides evenly; equal split distributes the paise-level rounding remainder deterministically so shares always sum exactly to the total; exact split rejects totals that don't match (and rolls back the created entry); exact split accepts a matching total; a non-member cannot be set as payer; all participants must be current group members; only the payer or the person who logged an expense can delete it. |
| `SettlementGenerationTests` | Net balances always sum to zero (conservation of money) across a multi-expense scenario; generated settlements, when hypothetically applied, bring every member's balance to exactly zero; regenerating settlements replaces the previous pending set (by id) rather than duplicating; only the payee can mark a settlement paid, not the payer; a settlement already marked paid is excluded from the next regeneration (its amount is netted out, not re-requested). |
| `ExpenseApiTests` | Full API round-trip: logging an expense, listing expenses, a non-member gets 404 (not 403, matching the existing `social` app convention of not revealing an account's existence), generating and listing settlements, mark-paid requires the actual payee (400 otherwise), the UPI link includes the payee's self-reported UPI ID when set and is `null` when not set, deleting an expense, and a `shared_pair` account correctly returns 404 for expense endpoints (the feature is group-accounts-only). |

Full suite coverage by app (unchanged apps summarized; see prior CHANGELOG entries for detail):

| App | What's covered |
|---|---|
| `accounts_app` | Registration, login, password hashing, MPIN set/verify, password reset flow, username lookup endpoint. |
| `wallet` | Gullak auto-creation/singleton enforcement, Decimal precision, block/unblock math, transfer conservation, double-submit idempotency, Gullak-leg exclusion from the general transaction list, shared-account contribute/unblock. |
| `goals` | Add-funds increment-only + over-allocation blocking (personal and shared-funded), automatic proportional emergency-unblock deduction, legacy manual-resolution path retained and tested. |
| `streaks` | Consecutive-day logic, idempotent check-ins, zero-activity streaks. |
| `social` | Invite send/accept/decline, pair/group membership rules, consent-based admin transfer, member removal, aggregate-only visibility, own-share-only unblock, no-cross-funding, smart split suggestion, per-goal contribution tracking, notification read/actioned lifecycle. |
| `expenses` (new) | See table above. |

## 2. Django system checks

```
python manage.py check  →  System check identified no issues (0 silenced)
```

## 3. Migrations

Three new migrations were generated (not hand-written) via `makemigrations` against the actual model changes, and applied cleanly to a fresh `db.sqlite3`:

- `accounts_app/migrations/0002_user_upi_id.py` — adds a nullable `upi_id` CharField to `User`, used to build settlement UPI deep-links. Nullable/blank by default — no data migration needed, fully backward-compatible.
- `social/migrations/0002_alter_notification_type.py` — adds `settlement_paid` to `Notification.type`'s choices (metadata-only change; `type` is already a plain CharField, so no column alteration).
- `expenses/migrations/0001_initial.py` — creates `ExpenseEntry`, `ExpenseShare`, `Settlement`, their indexes (`account`+`expense_date`, `account`+`status`), and the `unique_share_per_expense_user` constraint.

`python manage.py makemigrations --check --dry-run` was run immediately before packaging and reported **no changes detected**, confirming the migrations fully capture the current model state. No existing V1/V2 migrations were altered or deleted — this is purely additive. An existing database can be migrated forward with a plain `python manage.py migrate`.

## 4. Frontend build & lint

```
npm install     →  succeeded, 60 packages, no install errors
npm run build   →  succeeded, no errors, 131 modules transformed
npx oxlint src  →  0 errors, 0 warnings on all new/modified files
```

One real lint warning was caught and fixed during this round: `GroupExpensesPage.jsx` initially imported `useNavigate` but never used it (leftover from an earlier draft) — removed, confirmed clean on the next lint+build pass. `SharedAccountDetailPage.jsx` carries one pre-existing `react-hooks(exhaustive-deps)` warning from before this update (its mount-only `useEffect` convention, consistent with other V1/V2 pages) — not introduced by this change and left as-is to match the codebase's existing pattern.

`node_modules/` and `dist/` were removed from the delivered project after the build check — the person runs `setup-frontend.bat` (or `npm install`) themselves per the setup instructions.

## 5. What was NOT independently verified

- **Visual/UI rendering**: no headless browser was available in this build environment. `GroupExpensesPage`, `SettlementsPage`, and the updated `ProfilePage`/`SharedAccountDetailPage` were verified via a clean production build, lint, and manual code review against the existing design-token system (`styles/tokens.css`) and component library (`ui.jsx`) — not a rendered screenshot. Please do a manual pass through both new screens after setup.
- **Actual UPI app hand-off**: the generated `upi://pay?...` link's format follows the standard UPI deep-link spec, but was not tested by actually opening it in a real UPI app (this build environment has no mobile device/UPI app access). Recommend a manual test on a phone with a UPI app installed before relying on it.
- **Actual deployment to Render.com**: `render.yaml` was not modified and was not re-deployed as part of this round.
- **Postman collection**: the new "Expenses - Group Split & Settlements" folder was validated as well-formed JSON and its requests mirror the exact API calls covered by the automated test suite, but it was not executed inside the Postman application itself.
- **Concurrency**: expense logging and settlement generation are wrapped in `db_transaction.atomic()` for internal consistency, but (matching the rest of this project's test suite) there are no multi-threaded concurrency tests for two members generating settlements simultaneously.

## 6. Design decisions made during this update (confirmed with the requester)

- **Split types**: equal and exact-amount splits only (percentage-based splitting deferred — see README's Future improvements).
- **Debt ledger is separate from the pooled balance**: logging a group expense never debits `Account.block_balance` or changes anyone's `SharedContribution.contributed_amount`. This was a deliberate choice to avoid interacting with the existing shared-account balance invariants (emergency-unblock caps, visibility rules, etc.) — expense-splitting and pooled-savings are treated as two independent concerns, the same mental-model split Splitwise-style tools use.
- **UPI ID is self-reported**: added as a plain, unvalidated `CharField` on `User` (no format verification, no bank integration) — used only to build the deep-link string. This matches the project's existing "no payment gateway" design for all other money movements.

## Summary

| Category | Status |
|---|---|
| Backend automated tests | ✅ 143/143 passing (20 new, 0 modified/removed) |
| Django system checks | ✅ Clean |
| Migrations | ✅ Clean, additive; `makemigrations --check` confirms nothing missing |
| Equal expense split (incl. rounding-remainder distribution) | ✅ Verified via tests |
| Exact-amount expense split (incl. total-mismatch rejection) | ✅ Verified via tests |
| Membership/permission gating (payer, participants, non-members) | ✅ Verified via tests |
| Debt-simplification settlement generation | ✅ Verified via tests (balance conservation, minimal transfer count) |
| Regeneration replaces pending, preserves paid history | ✅ Verified via tests |
| Payee-only "mark paid" confirmation | ✅ Verified via tests |
| UPI deep-link generation (with/without UPI ID set) | ✅ Verified via tests |
| shared_pair accounts correctly excluded from this feature | ✅ Verified via tests |
| Frontend build | ✅ Clean |
| Frontend lint | ✅ Clean (0 errors, 0 new warnings) |
| Live deployment to Render | ⚠️ Not performed — unchanged, config not re-verified this round |
| Visual UI review | ⚠️ Code-reviewed, not screenshot-tested |
| Real UPI app hand-off | ⚠️ Not testable in this environment — recommend manual phone test |

---

## V2.3 verification — Standalone `splits` app (backend only)

### 1. What was verified

| Check | Result |
|---|---|
| `python manage.py makemigrations splits` | ✅ Clean single initial migration, no missed model changes |
| `python manage.py migrate` (fresh DB) | ✅ Applies cleanly, including all pre-existing apps' migrations |
| `python manage.py check` | ✅ No issues |
| `splits/tests.py` | ✅ 36/36 passing |
| Full project test suite (`python manage.py test`) | ✅ 179/179 passing (143 pre-existing + 36 new), 0 modified/removed |

### 2. Areas covered by the 36 new tests

- Equal split (even division + rounding-remainder distribution)
- Custom split (exact amounts, rejects totals that don't match)
- Percentage split (rejects totals ≠ 100%, computes Decimal shares with rounding)
- Non-member blocked from creating expenses; participants must be group members
- Membership: adding a member, self-leave, creator-only removal of others, creator cannot be removed
- Settlement generation: GLOBAL (debt-simplification, balance conservation) and PAIRWISE (direct net per pair) modes
- Recalculation clears stale pending settlements while preserving paid history
- Payee-only "mark paid" authorization
- UPI ID format validation (accept/reject)
- UPI payment-info includes a deep link only when the payee has a UPI ID set
- API-level: group creation, members-only 404 gating (including unauthenticated → 401), expense creation, non-member rejection, full recalculate→mark-paid flow, leaving a group, UPI save (valid/invalid)
- Pending-settlement-total on the group list (before and after recalculation)
- Settlement-mode PATCH: rejected for non-creator, accepted for creator
- Username lookup: found (returns id) and not-found cases

### 3. What was NOT independently verified

- **Actual UPI app hand-off**: link format follows the standard UPI deep-link spec but wasn't opened in a real UPI app (no mobile device in this environment).
- **Postman collection**: not created for this app (not requested; the `expenses` app's existing collection covers the same UPI-link pattern).
- **Concurrency**: `generate_settlements()` and `create_expense()` use `db_transaction.atomic()` for internal consistency; no multi-threaded concurrency tests were run (consistent with the rest of this project's test suite).
- **Frontend**: no automated UI/browser tests exist anywhere in this project (V1 or V2) — verification below is build/lint-level, not click-through.

### 4. Design decisions confirmed with the requester before building (backend)

- **Standalone architecture**: `SplitGroup` is fully independent of `wallet.Account` and the `social` app (no wallet balance, no invite-acceptance flow) — chosen over integrating with the existing shared-account infrastructure, to match the literal spec and avoid any risk to existing features.
- **UPI/QR**: backend returns the UPI link + structured fields only; QR image rendering is left to the frontend, so no new dependency (e.g. `qrcode`/`Pillow`) was added to the backend.
- **Member removal**: the creator can remove any member; any other member can remove only themselves (leave).

---

## V2.3 frontend verification — `features/splits/` (six screens)

### 1. What was verified

| Check | Result |
|---|---|
| `npm install` (adds `qrcode`) | ✅ Installs cleanly, no peer-dependency errors |
| `npx oxlint` on every new/changed file | ✅ 0 warnings, 0 errors |
| `npm run build` (production Vite build) | ✅ Succeeds; `qrcode` confirmed code-split into its own chunk (not in the initial bundle) |
| Backend full test suite, re-run after the 3 small API additions + 1 serializer fix made while wiring the frontend | ✅ 179/179 passing |

### 2. Small backend additions made while building the frontend (all additive, documented in CHANGELOG.md)

Building the six screens surfaced gaps the original API design (approved before this round) didn't cover:

- `pending_settlement_total` on `GET /api/splits/groups/` — needed for the "₹X pending" line on the Split Groups screen. Implemented as a correlated subquery (not a second join) to avoid the classic Django annotate-fan-out bug when combined with the existing `members__user` filter.
- `PATCH /api/splits/groups/<id>/` — needed so the Group Detail screen's settlement-mode radios can actually persist a change (creator only).
- `GET /api/splits/users/lookup/?username=` — needed for "Add Member": the existing `accounts_app` username lookup deliberately hides the user id (its invite flow requires acceptance), which doesn't work for this app's direct-add model.
- **Bug caught before shipping**: `SplitExpenseSerializer.paid_by`/`created_by` returned bare ids; the frontend (matching the `expenses` app's established convention) expected nested `{id, username}` objects. Fixed at the source rather than working around it in the frontend.

All four are covered by new backend tests (see the 36-test breakdown above) and by the frontend code paths that call them.

### 3. What was NOT independently verified

- **No manual click-through / browser testing** — this environment has no browser. Verification is limited to: the code compiling and lint-passing, the API contracts it calls being exercised by passing backend tests, and careful manual review of each data shape (e.g. catching the `paid_by` nesting mismatch above).
- **UPI app / QR scan hand-off**: not tested against a real UPI app or phone camera.
- **Cross-browser/device rendering**: not verified beyond the CSS following the same responsive patterns (`ui.css`, `tokens.css`, bottom-nav/side-rail breakpoints) already used and verified elsewhere in this project.
- **No automated frontend tests** — consistent with the rest of this project, which has no frontend test suite (V1 or V2).

### 4. Design decisions made while building (frontend)

- **Folder structure**: used `features/splits/` (one folder per screen) exactly as specified, rather than this project's usual flat `pages/` convention — kept isolated since this is explicitly a self-contained, independently-owned feature area.
- **QR codes**: generated client-side with the `qrcode` package, dynamically imported so it doesn't add to the initial bundle. No server-side QR image generation, no external QR-image service (avoids leaking UPI IDs/amounts to a third party).
- **"Show Calculation"**: computed client-side from already-loaded expense data rather than adding a new backend endpoint — see the README's `splits` guide for how `pairwise` vs. `global` groups are explained differently.
- **Navigation**: added a "Splits" entry to both the desktop side rail and mobile bottom nav, following the same pattern already used for "Shared".

---

## V2.3.1 verification — Settlement Mathematics Module (`splits/services/settlement.py`)

### 1. What was verified

| Check | Result |
|---|---|
| `python manage.py check` after the `services.py` → `services/` package refactor | ✅ No issues |
| Full pre-existing `splits` test suite (82 tests: 36 original + 46 new), unmodified, re-run after the refactor | ✅ 82/82 passing — confirms the package split is 100% backward-compatible (no call site in `views.py`, `permissions.py`, or existing tests needed to change) |
| Full project test suite (`python manage.py test`) | ✅ 225/225 passing (179 pre-existing + 46 new), 0 modified/removed |

### 2. Areas covered by the 46 new tests (`splits/test_settlement.py`)

Pure-function tests (no database):
- Equal split: even division, the four required rounding cases (₹100/3, ₹100/6, ₹10/3, ₹0.01/3), single-participant, empty-list, and a sweep across a wider range of amounts/participant counts confirming shares always sum exactly to the total
- Custom split: accepts matching totals, rejects mismatches/missing participants/negative shares/empty input
- Percentage split: accepts 100%-summing splits, rejects totals ≠ 100%, handles rounding, rejects negative percentages
- Pairwise netting: mutual debts cancel to a single net, equal mutual debts fully cancel, one-directional debts pass through unchanged, same-direction debts accumulate, independent pairs stay independent, negative amounts represent repayments, sub-paisa residue is dropped, empty input produces no result
- Global simplification: two-debtors-one-creditor, pass-through balances aren't routed through a zero-balance member, sub-paisa balances ignored, all-zero produces nothing, uneven three-way splits settle completely, result sums conserve total money

Integration tests (real groups/expenses/settlements):
- Multiple expenses accumulate into one settlement
- Mutual debts across two expenses net down correctly
- Zero net balance produces no settlement
- Uneven division (3-way split of ₹100) settles exactly with no leftover
- Four-member group global settlement (3 transfers, correct total)
- Already-paid settlements reduce future balances correctly in both GLOBAL and PAIRWISE modes
- Show Calculation: expense-level breakdown matches the required format exactly (including the project's own Dinner/Manav/Rahul/Amit example), payer's own share excluded from the debts list, pairwise settlements list only the relevant expenses, global settlements include the full ledger plus correct per-person net, group-wide trail is ordered oldest-first
- API: the new calculation endpoint returns the expected shape; non-members get 404

### 3. What was NOT independently verified

- **No changes made to the frontend in this round** — the existing client-side "Show Calculation" (built in the V2.3 frontend round) still works as before and was not switched to call the new backend endpoint; that would be a frontend-ownership decision for a future round. The note in the V2.3 frontend verification section above ("computed client-side... rather than adding a new backend endpoint") describes what was true for that round — a backend endpoint now exists as of this round, but nothing currently consumes it from the UI.
- **Formal optimality proof for global simplification**: the greedy largest-debtor-vs-largest-creditor match is the standard approach used by Splitwise-style apps and is minimal for the common case (one connected component of balances), but no formal proof of global minimality across all possible balance graphs was attempted — consistent with how this algorithm is normally implemented in practice.

### 4. Design decisions made while building

- **Package structure**: `services.py` → `services/` was chosen over adding a `services/settlement.py` alongside a now-inconsistent flat `services.py`, so every submodule (not just settlement math) has a clear, single responsibility — matching the spirit of "a clean service module Person 1's APIs can call," not just the letter of it.
- **Backward compatibility over a cleaner call style**: `services/__init__.py` re-exports everything so existing code keeps calling `services.create_group(...)` etc. unchanged, rather than requiring every call site to be rewritten as `services.groups.create_group(...)`. This was chosen to minimize risk to already-shipped, already-tested code — the internal module boundary is what matters for "ownership," not the exact import spelling call sites use.
- **`net_pairwise_debts`/`simplify_global_debts` as pure functions**: deliberately take plain tuples/dicts rather than Django querysets, so they're fast to test and reusable outside a request/response cycle (e.g. they'd work identically if `splits` ever needed to preview a settlement before persisting it).
- **"Show Calculation" scope**: a new read-only API endpoint was added (not requested as an explicit endpoint in the original Person 1 API list, but required by the project's explicit "explainability" requirement) rather than only leaving it as an internal function — Person 1's views layer calls straight into `services.explain_settlement()`, matching the "clean service Person 1's APIs can call" brief literally.

---

## V2.4 verification — Dashboard Analytics (Net Worth Over Time & Spend by Category)

### 1. What was verified

| Check | Result |
|---|---|
| `python manage.py check` | ✅ No issues |
| `wallet` app test suite (56 tests: 28 pre-existing + 19 analytics + 9 CSV export from the next round) | ✅ passing |
| Full project test suite | ✅ 244/244 at the end of this round (225 pre-existing + 19 new) |
| Fresh `seed_demo_data` run, output spot-checked | ✅ `net_worth_history()` produced a real 20-day curve (36,400 → 46,314, varying day to day); `spend_by_category()` produced a 5-category breakdown (Transport/Shopping/Other/Food/Bills) — both against real backdated demo data, not just unit-test fixtures |
| `npx oxlint` on new/changed frontend files | ✅ 0 warnings, 0 errors (whole-`src` lint showed only 6 pre-existing warnings, none from this round's files) |
| `npm run build` | ✅ Succeeds; initial build flagged a 785KB main bundle from `recharts` — fixed via `React.lazy`/`Suspense`, confirmed in the rebuilt output that `recharts` now ships as its own ~330KB chunk and the main bundle dropped to 405KB |

### 2. Areas covered by the 19 new backend tests

- `net_worth_history`: flat history with no transactions, oldest-first ordering and date range, an expense today raising the reconstructed past net worth by the exact amount, income today lowering it, a backdated expense only affecting dates before it (not on/after), a transfer between the user's own accounts not changing history at any point, Revenue Generation/Loan-Debt accounts held constant across every day, `days` parameter controlling result length
- `spend_by_category`: aggregation by category, largest-first ordering, categories with no spending omitted (not zero), income/lend correctly excluded from "spend", transactions outside the day window excluded
- API layer: response shape for both endpoints, `days` param clamping to a sane range (1–365), invalid `days` falling back to the default, authentication required, and — importantly — that one user's analytics never reflect another user's accounts

### 3. What was NOT independently verified

- **No claim of historical accuracy for Revenue Generation / Loan-Debt accounts** — this is a documented approximation (see README), not something that could be "verified" against ground truth, since this app has no ledger for those account types.
- **Chart rendering itself** — no browser in this environment, so the actual visual output of `NetWorthChart`/`SpendByCategoryChart` (colors, responsiveness, tooltip behavior) was reviewed by code inspection against `recharts`' documented API, not visually confirmed.

### 4. Design decisions made while building

- **No new Django app**: both endpoints were added to the existing `wallet` app (where `Account`/`Transaction` already live) rather than creating a dedicated `analytics` app, since two aggregation functions didn't justify the overhead, and Person 4's brief was explicitly "do not rebuild the dashboard" — minimal footprint was the goal.
- **Real categories, not the example's categories**: the task's example showed Food/Travel/Shopping/Bills/Entertainment/Other, but the existing `TransactionCategory` enum has Food/Transport/Bills/Shopping/Other/Uncategorized. Used the real enum rather than adding new categories, since "don't touch Transactions CRUD" was an explicit boundary and changing the category choices would ripple into the create-transaction form, filters, and existing data.
- **Demo-data backdating via `.update()`, not a model change**: `Transaction.timestamp` is `auto_now_add=True` by design (a real transaction should always be timestamped "now"). Rather than loosening that for demo purposes, the seed script backdates via a raw `QuerySet.update()` call after creation, which bypasses `auto_now_add` without touching the model or the real transaction-creation flow at all.

---

## V2.5 verification — CSV Export + Password-Reset Email

### 1. What was verified

| Check | Result |
|---|---|
| `python manage.py check` | ✅ No issues |
| `accounts_app` test suite (15 tests, including the rewritten/expanded `PasswordResetTests`) | ✅ passing |
| `wallet` test suite (56 tests, including 9 new CSV export tests) | ✅ passing |
| Full project test suite | ✅ 259/259 (250 pre-existing + 9 new) |
| `python manage.py shell` check of `settings.EMAIL_BACKEND`/`FRONTEND_URL`/`PASSWORD_RESET_TIMEOUT` after adding `FRONTEND_URL` to `.env` | ✅ confirmed defaults resolve correctly (console backend when no SMTP creds set) |
| `npx oxlint` on changed frontend files | ✅ 0 warnings, 0 errors |
| `npm run build` | ✅ Succeeds |

### 2. Areas covered by the 9 new CSV export tests

Content-Type/Content-Disposition headers, header row column names, correct data per row (date/type/category/amount/account/description), Gullak-leg exclusion by default, `include_gullak=true` including them, the `type` filter being respected, exports being scoped to the requesting user only (another user's transactions never leak in), authentication required, and an empty export still returning just the header row.

### 3. Areas covered by the rewritten/expanded password-reset tests (2 → 8)

Full reset flow now parses the real emailed link (not a response field) and round-trips it through the confirm endpoint into a working login; the response never contains `dev_uid`/`dev_token`; the response is byte-for-byte identical whether the email exists or not; a token is rejected after being used once (single-use, via Django's built-in password-hash-in-hash mechanism); an invalid token is rejected; a malformed uid is rejected; the emailed link points at the configured `FRONTEND_URL`; and — a genuinely useful case caught by writing this test — a simulated SMTP failure (mocked `EmailMultiAlternatives.send` raising) still returns the same generic 200 response rather than a 500 or an error that would reveal whether sending failed.

### 4. Bugs found and fixed while building this round (not pre-existing verification gaps — introduced and caught within this same round)

- **Template auto-escaping mangled the reset link**: Django's template engine HTML-escapes `&` to `&amp;` by default regardless of file extension, so the plain-text email's `uid=...&token=...` link was broken until `{% autoescape off %}` was added to the `.txt` template. Caught by the new tests failing with `KeyError: 'token'` when parsing the (corrupted) link.
- **Shared throttle cache breaking test isolation**: expanding `PasswordResetTests` to 8 tests (several hitting the `auth`-throttled endpoints multiple times each) exhausted the 10/min `auth` scope's shared `LocMemCache` budget within a single test run, causing the alphabetically-later `RegistrationLoginTests.test_register_and_login` to fail with an unrelated 429. Fixed by clearing the cache in `PasswordResetTests.setUp`/`tearDown` — scoped narrowly to the class causing the exhaustion, rather than changing throttle behavior project-wide.
- **Pre-existing (not introduced this round) bug fixed opportunistically**: `TransactionsPage.jsx`'s empty-state action called `navigate('/add')` without `useNavigate` ever being imported — a `ReferenceError` waiting to happen the first time a user with zero transactions clicked "Add transaction" from that empty state. Fixed in passing since the file was already being edited for the Export CSV button.

### 5. What was NOT independently verified

- **No real SMTP send was performed** — no real mail server credentials exist in this environment. Verified instead: (a) the console backend actually prints emails correctly (used throughout manual testing), (b) `EmailMultiAlternatives` is constructed with the correct `to`/`subject`/`body`/HTML-alternative and its `.send()` is actually called (verified via `django.core.mail.outbox` in tests, which Django's test runner backs with the `locmem` backend regardless of what `.env` specifies), and (c) the settings correctly select SMTP vs. console based on whether `EMAIL_HOST_USER` is set. Actually configuring a real Gmail/SendGrid account and confirming an email lands in an inbox would need real credentials this environment doesn't have.
- **Email client rendering of the HTML template** — reviewed by eye against standard "email-safe HTML" conventions (table-based layout, inline styles, no external assets) but not rendered in an actual email client (Gmail/Outlook/etc. all have their own CSS quirks).

