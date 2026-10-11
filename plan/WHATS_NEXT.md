# What's next

**State (2026-10-11):**
- The specification is drafted (`docs/SPECIFICATION.md`). It hasn't been submitted to Moodle yet; the deadline is the end of week 6.
- Stages 01–03 are accepted (scaffold, money and split rules, balances and settle-up), and the gate is green.

**Next:**
1. Main writes `plan/04_persistence_auth.md` (SQLAlchemy, Alembic, register and login, AC5 and AC8). This needs dependency decisions; see `PLAN.md` D7 and D8.
2. Stage 04 must resolve the `httpx` → `httpx2` TestClient deprecation warning.
3. The user removes the stale root `.venv` and points the IDE interpreter at `backend/.venv`.
