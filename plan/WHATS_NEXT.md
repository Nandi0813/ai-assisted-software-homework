# What's next

**State (2026-10-11):**
- The specification is drafted (`docs/SPECIFICATION.md`). It hasn't been submitted to Moodle yet; the deadline is the end of week 6.
- Stages 01–05, 05b and 06 (tool A) are accepted, and the gate is green. Backend: 233 tests, 100% coverage, 0 warnings. `make dev` starts both servers, and the README documents setup.
- The grading-gap items are planned: D13 (dual-tool), D14 (working methods), D15 (`docs/AI_USAGE.md` log) and D16 (the `gate` and `stage-spec` skills). The stage index runs 05–10.

**Next:**
1. The user runs Antigravity on the worktree `../hw-compare-06-antigravity` (branch `compare/06-antigravity`, base `82b3ef0`) and records start and end times and interventions. Then main reviews and gates it and writes the D13 comparison.
2. Main writes `plan/06b_leave_rejoin.md` (AC7), and removes the unused `LedgerService._users`.
3. The user writes or confirms the ✍️ decision reasons in `docs/AI_USAGE.md`.
4. The user removes the stale root `.venv`, points the IDE interpreter at `backend/.venv`, and pushes the local commits.
