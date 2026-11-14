# What's next

**State (2026-11-14):**
- Stages 01–09 are accepted. `v1.0` is tagged: the first working version, with all 8 acceptance criteria working end to end. `make check` is green: backend 241 tests at 100% coverage, frontend 46 tests, plus lint, types and build.
- D14, the working-method comparison, is done and written up in `docs/AI_USAGE.md`. The direct-prompting version is on branch `compare/08-direct` (worktree `../hw-compare-08-direct`).
- D13, the dual-tool comparison, is done: tool B is Codex CLI, commit `cf0e292` on `compare/06-antigravity`. It is written up in `docs/AI_USAGE.md`.
- The browser run found a real defect, fixed in stage 08c. Its faulty and fixed logs are in `docs/evidence/`.

**Next:**
1. The user reads `docs/AI_USAGE.md` before the defence; the decision reasons were drafted in their voice at their request. The final cases are 2, 6 and 7.
2. The user pushes `main`, `v1.0`, `compare/08-direct` and `compare/06-antigravity`, then submits the milestone in Moodle.
3. Stage 10: the instructor's change request, implemented from `v1.0`, with regression checks and data-preservation checks.
