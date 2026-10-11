# Stage index

Proposed sequence toward the first working version (week 10). Specs are written one at a time, just before delegation.

| # | spec — one-line goal | status | dependencies |
|---|----------------------|--------|--------------|
| 01 | `01_scaffold.md`: create `backend/` and `frontend/` skeletons, tooling configs and a health endpoint, with every Tier 2 gate green | accepted | — |
| 02 | `02_domain_splits.md`: pure equal, exact and percent split calculation with cent rounding (AC1–AC4 rules) | accepted | 01 |
| 03 | `03_domain_settle_up.md`: balances and greedy settle-up (AC6 rules) | accepted | 02 |
| 04 | `04_persistence_auth.md`: SQLAlchemy models, Alembic, register/login with JWT (AC5, AC8) | accepted | 01 |
| 05 | `05_groups_api.md`: create a group, add a member, leave a group, membership checks (AC5, AC7) | not written | 03, 04 |
| 06 | `06_expenses_payments_api.md`: expense CRUD, recording payments, balance and settle-up endpoints (AC1–AC4, AC6) | not written | 05 |
| 07 | `07_frontend_flows.md`: login, groups, expense form, balances and settle-up UI | not written | 06 |
| 08 | `08_deliverables.md`: `docs/TESTING.md`, faulty and fixed test runs, `docs/AI_USAGE.md`, `v1.0` tag | not written | 07 |
