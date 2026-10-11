# What's next

**State (2026-10-11):**
- The specification is drafted (`docs/SPECIFICATION.md`). It hasn't been submitted to Moodle yet; the deadline is the end of week 6.
- Stages 01–05 are accepted, and the gate is green. Backend: 174 tests, 100% coverage, 0 warnings.
- The grading-gap items are planned: D13 (dual-tool), D14 (working methods), D15 (`docs/AI_USAGE.md` log) and D16 (the `gate` and `stage-spec` skills). The stage index runs 05–10.

**Next:**
1. Main writes `plan/06_expenses_payments_api.md` with the `stage-spec` skill. It is built twice (D13): the implementer on `main` and Antigravity on `compare/06-antigravity`, both from the same base commit.
2. Before stage 06: the user checks that Antigravity can open this repo and reads `AGENTS.md`, for D13.
3. The user writes or confirms the ✍️ decision reasons in `docs/AI_USAGE.md`.
4. The user removes the stale root `.venv`, points the IDE interpreter at `backend/.venv`, and pushes the local commits.
