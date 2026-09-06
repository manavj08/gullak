# Gullak V2 — Project Summary

## What it is
A personal **and shared** money-management app. Track daily spending across multiple accounts, deliberately "block" money into your Gullak (a real account of its own), set savings goals funded from it, build a daily check-in streak — and now save together with a partner or a group for something specific, with invites, a notification center, and a smart split suggestion.

## Technology stack
- **Backend**: Django 5.1 + Django REST Framework, SQLite, SimpleJWT, Argon2 password hashing
- **Frontend**: React 19 + Vite, React Router, Axios, `qrcode` (client-side QR for split settlements), `recharts` (dashboard charts, lazy-loaded)
- **Deployment target**: Render.com (free tier) — blueprint included
- Requires **Python 3.11+**

## User roles
- **Authenticated user** — scoped to their own personal data (unchanged from V1)
- **Shared account member** — participant in a Relationship (pair) or group account
- **Group admin** — group accounts only; manages membership and can initiate a consent-based admin-role transfer. Pair accounts have no admin — two equal partners.
- Django admin (`/admin/`) available separately for the project owner via `createsuperuser`

## Quick start (Windows)
1. Run `setup.bat` (backend) then `setup-frontend.bat` (frontend)
2. Run `run.bat` and `run-frontend.bat` in two separate windows
3. Open http://127.0.0.1:5173 — you'll land on the public landing page; use **Sign in** or **Get started**
4. Log in: **demo@gullak.app** / **Demo@12345** (MPIN: 1234) — or the second demo user, **demo2@gullak.app** / **Demo@12345**, to see the shared-account flow from the other side

## Key features (V1, carried forward)
- **Gullak is a real account** — its own card in the Accounts list, its own detail page, its own block/unblock transaction history
- 4 other account categories (Daily Transaction, Savings, Revenue Generation, Loan/Debt)
- Block/Unblock savings mechanic with an emergency-unblock confirmation step
- Live Gullak total, allocated, and unallocated breakdown (always current, never stale)
- Income/Expense/Lend/Borrow/Transfer transactions with double-submit protection; Gullak block/unblock movements are kept separate from this general list
- Accounts page Grid/Scroll layout toggle, remembered per device
- Dedicated Transactions history page with type filters
- Timezone-safe daily streak counter
- MPIN quick-unlock, required on every app open/reload

## Key features (new in V2)
- **Public landing page** at `/` explaining the app, with Login/Register CTAs; an already-logged-in visitor is redirected straight past it
- **Global page header** on every screen — back arrow (top-left), page title, notification bell with unread badge (top-right)
- **Shared (Relationship) accounts** — 2 people, no admin, equal partners
- **Family & Friends group accounts** — 2+ people, admin-managed, with an optional occasion name/date and reminder toggle
- **Username-based invites** — must be explicitly accepted; no one can be added without their approval
- **Aggregate-only visibility** — your own contribution is always shown in full, both for a shared account's overall pool and for an individual common goal; everyone else's is only ever a single combined total, enforced server-side
- **Own-share-only emergency unblock** — capped at what you personally contributed, no consent step needed since it's your own money
- **No cross-funding** — a goal is funded from personal Gullak or a shared account, never both
- **Smart Gullak-split suggestion** — proposes how to split a new deposit across underfunded goals by urgency, capped at your live unallocated Gullak, with an option to also include a shared account's common goals (capped separately against that account's own pool), fully editable before applying
- **Automatic emergency-unblock deduction** — overage is now split proportionally across underfunded personal goals automatically, with an informational notification (replaces V1's manual "which goal should this come from" step)
- **Notification Center** — invites, admin-transfer requests, member joined/left, admin changed, goal-deduction notices; reached via the header's bell icon, unread badge refreshed on navigation
- **Group Expense Split & UPI Settlement** (group accounts only) — log a shared expense and split it equally or by exact custom amounts; generate the minimal "who owes whom" settlement list via debt-simplification; pay via a UPI deep-link built from the payee's self-reported UPI ID; the payee manually confirms once actually paid. A separate debt ledger — doesn't touch the shared account's pooled balance or contributions.
- **Standalone split groups** (new `splits` app, `/api/splits/`, full UI at `features/splits/`) — Splitwise-style splitting independent of wallet accounts: create a group with anyone directly, split equal/custom/percentage, choose fewest-payments (GLOBAL) or detailed (PAIRWISE) settlement mode, and pay via a UPI link or client-side-generated QR code. All settlement math (rounding, pairwise netting, global simplification, "Show Calculation" explainability) lives in its own `splits/services/settlement.py` module.
- **Dashboard analytics** — Net Worth Over Time (area chart) and Spend by Category (bar chart), backed by two new read-only aggregation endpoints in `wallet`
- **Transaction CSV export** — filter-aware download from the Transactions page
- **Real password-reset email** — SMTP if configured via env vars, Django's console backend otherwise; single-use, 1-hour-expiry link, no token ever exposed in an API response

## Important notes
- **Money is stored as exact Decimal rupees** (never paise, never floats) — the API works entirely in rupees end to end
- **Password reset sends a real email** — SMTP if `EMAIL_HOST_USER`/`EMAIL_HOST_PASSWORD` are set, otherwise Django's console backend (prints to the server log) for local dev/demos with zero config — see README for setup
- **Net Worth Over Time is exact for cash accounts, approximated for Revenue Generation / Loan-Debt** — those two account categories have no dated transaction ledger in this app (their value is a direct field, not built from transactions), so their *current* value is held constant across the whole chart range rather than guessed at
- **The V1 manual pending-deduction resolution flow still exists in the codebase and is fully tested**, but the live emergency-unblock flow now calls the new automatic version instead — see CHANGELOG.md for why
- **Notification sync is refresh-on-navigation, not real-time** (no WebSocket/polling infrastructure added) — a deliberate simplicity choice; see README's Future improvements
- **Shared-account visibility is aggregate-only by design** — there is intentionally no way to see another member's individual contribution, even for an admin
- **Group expense splitting is a separate debt ledger** — logging an expense never changes the shared account's pooled `block_balance` or anyone's `contributed_amount`; it only tracks who owes whom
- **No real UPI payment gateway is integrated** — the "Pay via UPI" button only opens a pre-filled `upi://pay?...` deep-link in the user's own UPI app; the app never verifies or moves money, and marking a settlement "Paid" is a manual, self-reported confirmation
- Free-tier Render deployment has cold starts and (without a paid disk) ephemeral SQLite storage — fine for demos, not for production financial data

## Where to look next
- `README.md` — full setup, architecture, troubleshooting, deployment steps, shared/group accounts guide
- `VERIFICATION.md` — what was tested and how, and what still needs manual review
- `CHANGELOG.md` — what changed and why, across all revisions
- `postman/` — ready-to-import API collection for `wallet`/`goals`/`streaks`/`social`/`expenses`/`accounts_app` (not yet extended to `splits`, analytics, or CSV export — see README Troubleshooting)
