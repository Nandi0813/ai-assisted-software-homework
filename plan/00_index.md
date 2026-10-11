# Stage index

Sequence toward the first working version (week 10), then the final version (week 13). Specs are written one at a time, just before delegation.

| # | spec — one-line goal | status | dependencies |
|---|----------------------|--------|--------------|
| 01 | `01_scaffold.md`: create `backend/` and `frontend/` skeletons, tooling configs and a health endpoint, with every Tier 2 gate green | accepted | — |
| 02 | `02_domain_splits.md`: pure equal, exact and percent split calculation with cent rounding (AC1–AC4 rules) | accepted | 01 |
| 03 | `03_domain_settle_up.md`: balances and greedy settle-up (AC6 rules) | accepted | 02 |
| 04 | `04_persistence_auth.md`: SQLAlchemy models, Alembic, register/login with JWT (AC5, AC8) | accepted | 01 |
| 05 | `05_groups_api.md`: create, list and show groups, add a member by username, membership checks returning 404, migration 0002 preserving existing data (AC5, AC8) | accepted | 03, 04 |
| 05b | `05b_dev_makefile.md`: root `Makefile` covering `make dev` (backend and frontend with reload, one command), test, lint, typecheck, format, check, migrate, reset-db, build, clean | accepted | 05 |
| 06 | `06_expenses_payments_api.md`: expense CRUD, recording payments, balance and settle-up endpoints, leaving a group with the non-zero-balance rule, restart persistence (AC1–AC4, AC6, AC7, AC8). **Built twice: implementer and Antigravity (D13)** | not written | 05 |
| 07 | `07_frontend_auth_groups.md`: register and login screens, token handling, group list, create group, add member, leave group | not written | 05 |
| 08 | `08_frontend_expenses.md`: expense form (equal, exact, percent), balances view, settle-up panel. **Settle-up panel built twice: spec-driven and direct prompting (D14)** | not written | 06, 07 |
| 09 | `09_deliverables_v1.md`: README setup, `docs/TESTING.md` mapping each criterion to its checks with manual steps, faulty and fixed test with both logs, explicit regression test, `docs/AI_USAGE.md` finalized, `v1.0` tag | not written | 08 |
| 10 | `10_change_request.md`: the instructor's change request, implemented from `v1.0` with regression and data-preservation checks | blocked (awaiting change request) | 09 |
