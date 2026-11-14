# What's next

**State (2026-11-14):**
- Stages 01–09 are accepted. `v1.0` is tagged: the first working version, with all 8 acceptance criteria working end to end. `make check` is green: backend 241 tests at 100% coverage, frontend 46 tests, plus lint, types and build.
- D14, the working-method comparison, is done and written up in `docs/AI_USAGE.md`. The direct-prompting version is on branch `compare/08-direct` (worktree `../hw-compare-08-direct`).
- The browser run found a real defect, fixed in stage 08c. Its faulty and fixed logs are in `docs/evidence/`.

**Next:**
1. **D13 (blocked on the user).** Run Gemini CLI as tool B on stage 06, in the worktree `../hw-compare-06-antigravity` (branch `compare/06-antigravity`, base `82b3ef0`). The auto-mode classifier refused the headless `gemini --approval-mode yolo` run, so the user must allow it or run it with `!`. Then main reviews it, gates it, commits it on the branch and writes "Dual implementation" in `docs/AI_USAGE.md`.
2. The user rewrites or confirms every ✍️ decision reason in `docs/AI_USAGE.md` and picks the final 3 decision cases. Strong candidates are 6, 7 and 5 or 2.
3. The user pushes `main`, `v1.0`, `compare/08-direct` and, once it exists, `compare/06-antigravity`, then submits the milestone in Moodle.
4. Stage 10: the instructor's change request, implemented from `v1.0`, with regression checks and data-preservation checks.
