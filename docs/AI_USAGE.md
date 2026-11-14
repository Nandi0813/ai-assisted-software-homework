# AI usage

> **Living document.** It is updated at every stage acceptance (`plan/PLAN.md` D15). Sections marked ✍️ must be written or confirmed by the author in their own words before submission.

## Tools and models

| Tool | Model | Role |
|------|-------|------|
| Claude Code (CLI) | Claude Opus 5.5 | **Main agent:** requirements analysis, architecture decisions, stage specs, code review, and the Tier 2 gate. It writes no application code (`AGENTS.md`). |
| Claude Code `implementer` subagent (`.claude/agents/implementer.md`) | Claude Haiku (low effort) | **Implementer:** transcribes one resolved stage spec into code and tests, then runs the focused checks. |
| Gemini CLI | Gemini (course-provided access) | The second implementation of stage 06, for the dual-tool comparison (D13). Run headless with the same spec and `AGENTS.md`. |
| Claude Code general-purpose subagent | Claude | Method 2 of the working-method comparison: built the settle-up panel from a conversational prompt with no spec (D14). |
| Playwright (via Claude Code MCP) | — | Main agent's browser run of the real app against the manual checks in `docs/TESTING.md`. |

## Working method

1. **Specification.** The main agent drafted `docs/SPECIFICATION.md` from the course requirements and the chosen topic. The author chose the topic and confirmed the interpretations.
2. **Architecture.** Decisions are recorded as D1–D16 in `plan/PLAN.md`. Each was proposed by the main agent and confirmed by the author.
3. **Stage loop.**
   - Main writes a fully resolved stage spec (`plan/NN_*.md`, using the `stage-spec` skill).
   - The implementer transcribes it and runs Tier 1 checks.
   - Main reviews the diff against the spec and runs the Tier 2 gate (the `gate` skill).
   - A receipt with commands, exit codes and coverage is appended to the spec.
   - The author authorizes each commit.
4. **Rules in the repo.** `AGENTS.md` (roles, validation tiers, invariants), `.claude/agents/implementer.md` and `.claude/skills/{gate,stage-spec}`.

## Phases where AI was used

| Phase | Evidence |
|-------|----------|
| Requirements analysis | `docs/SPECIFICATION.md` (topic ideation, acceptance criteria, uncertainties) |
| Design | `plan/PLAN.md` D1–D16 |
| Implementation | stages 01–08c (`plan/0*_*.md`): backend 01–06b, frontend 07–08c |
| Testing | the test lists in each spec's section 6; the receipts in each spec; `docs/TESTING.md`; the browser run that found defect 08c (`docs/evidence/e2e-group-page.png`) |
| Review | the "Spec gap" and "Minor finding" entries in the receipts for stages 02 and 04 |

## Decision cases

Candidates are collected as the work proceeds. The final submission uses three of them.

### Candidate 1: money representation (stages 02 and 04)

- **Problem.** Splitting amounts and accumulating balances in binary floating point loses cents. For example, `0.1 + 0.2 != 0.3`, and 100.00 / 3 cannot be represented exactly.
- **Tool.** Claude Code main agent (Opus 5.5).
- **Context and key instruction.** "Shares must always add up exactly to the total" (AC2) and "an amount with more than 2 decimals is rejected" (AC4).
- **AI suggestion.**
  - Store integer cents everywhere inside the backend.
  - Exchange decimal strings at the API.
  - Parse with a regex rather than `float()` or `Decimal`, so that `"1e3"`, `"NaN"` and `"1.234"` are rejected by format rather than by arithmetic (PLAN D4).
- **Decision.** ✍️ Accepted. *(Author: write why in your own words.)*
- **Verification.**
  - `backend/tests/domain/test_money.py::test_ac4_parse_amount_rejects_bad_format`
  - `::test_parse_format_round_trip`
  - `backend/tests/domain/test_splits.py::test_split_equal_shares_always_sum_to_total` (28 combinations)
- **Limitations.** One currency per group, a maximum of 1,000,000.00, and no currency conversion.

### Candidate 2: settle-up algorithm (stage 03)

- **Problem.** "Settle up with the fewest transfers." Finding the true minimum is NP-hard: it reduces to partitioning the balances into the largest number of zero-sum subsets.
- **Tool.** Claude Code main agent.
- **Context and key instruction.** The "Settle-up" acceptance criterion.
- **AI suggestion.** Use a greedy algorithm that repeatedly matches the largest creditor with the largest debtor, breaking ties by join order. Guarantee at most n−1 transfers rather than the true minimum, and reword AC6 accordingly (PLAN D6).
- **Decision.** ✍️ Accepted, and the spec wording was changed. *(Author: explain the trade-off of determinism and simplicity against optimality.)*
- **Verification.**
  - `backend/tests/domain/test_balances.py::test_ac6_recording_transfers_settles_everyone`: 5 balance sets, each checked for ≤ n−1 transfers and for every balance reaching 0 after the transfers are applied.
  - `::test_ac6_settling_through_payments_zeroes_compound_balances`
- **Limitations.** The result is not always the absolute minimum when the balances contain independent zero-sum subgroups.

### Candidate 3: ASCII-only digits in the amount parser (stage 02)

- **Problem.** Python's regex `\d` also matches non-ASCII digits, such as Arabic-Indic `١`. `int()` would then silently accept input like `"١.00"`.
- **Tool.** Claude Code main agent (spec), then the implementer (Haiku).
- **AI suggestion.** Use `[0-9]` instead of `\d`, with an explicit test case. During implementation, Ruff rule RUF001 flagged the literal character in the test file. The implementer wrote it as the escape `"١.00"` instead of adding a forbidden `noqa`.
- **Decision.** ✍️ Accepted, along with the implementer's deviation.
- **Verification.** `backend/tests/domain/test_money.py::test_ac4_parse_amount_rejects_bad_format[١.00]`, and the stage 02 receipt.

### Candidate 4: test client deprecation (stages 01 and 04)

- **Problem.** The stage 01 gate showed `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`
- **Options.** Filter the warning; pin older versions; or swap the dev dependency `httpx` for `httpx2`.
- **AI suggestion.** Defer the fix to stage 04, which changes dependencies anyway. Verify against Starlette's source (`starlette/testclient.py`, which tries `import httpx2` first) before switching.
- **Decision.** ✍️ Accepted.
- **Verification.** The stage 04 receipt: `152 passed`, warning count 0 in `.logs/04-gate-pytest.log`.

### Candidate 5: rejecting an implementer shortcut (stage 05)

- **Problem.** The spec didn't name the type of a parametrized test argument. The implementer (Haiku) chose `dict[str, Any] | None` to satisfy `mypy --strict`, and flagged it as a hazard itself.
- **Tool.** Claude Code `implementer` (Haiku), then main review (Opus 5.5).
- **AI suggestion.** Keep `Any`; it type-checks.
- **Decision.** ✍️ Rejected. `AGENTS.md` forbids `Any` without an inline reason, and every request body in the tests has only `str` values, so `dict[str, str] | None` is precise. The fix went through Addendum 05-A to the same implementer, not as a manual edit.
- **Verification.** `uv run mypy` passed with no issues in 31 files after the change (stage 05 receipt). `grep Any backend/tests/test_groups.py` finds nothing.
- **Lesson.** A gap in the spec turns into a type the implementer chose itself; the stage-spec checklist now has to name parameter types.

### Candidate 6: a real defect found by an agent's verification (stage 05b)

- **Problem.** While verifying the new `Makefile`, the implementer ran `make reset-db`, and `uv run alembic upgrade head` failed with `ModuleNotFoundError: No module named 'app'` (`backend/app/migrations/env.py:6`). The whole suite (174 tests) was green, because pytest's `pythonpath = ["."]` hid the problem; the Alembic CLI branch had never run.
- **Tool.** Claude Code `implementer` (Haiku). It stopped as its rules require instead of working around the problem. Main (Opus 5.5) then diagnosed it and planned the fix.
- **AI suggestion.** Two options. Hack `sys.path` inside `env.py`, or use Alembic's documented `prepend_sys_path = %(here)s` together with `path_separator = os`. The second is needed because the repo path contains spaces, which Alembic would otherwise split on. The plan also required a regression test that runs the CLI in a subprocess **before** applying the fix.
- **Decision.** ✍️ Accepted the configuration fix and rejected the `sys.path` hack.
- **Verification.**
  - `backend/tests/test_migrations.py::test_alembic_cli_upgrade_runs_outside_pytest_path`.
  - The run against the faulty version: `docs/evidence/05b-alembic-cli-regression-before.log`, exit 1.
  - The run against the fixed version: `docs/evidence/05b-alembic-cli-regression-after.log`, exit 0.
  - **This is the faulty-vs-fixed test evidence required by the testing criterion. The defect occurred for real; it was not planted.**
- **Limitation.** The test shells out to `sys.executable -m alembic`, so it depends on the virtualenv being complete.

### Candidate 7: a browser run catches what 44 green tests missed (stage 08c)

- **Problem.** After stage 08 every gate was green (44 frontend tests). The main agent then drove the real app in a browser (Playwright) along the manual steps of `docs/TESTING.md`. Creating a group, adding bob and carol, then adding "Dinner" 90.00 equal split charged **alice only**: balances stayed `0.00`, so AC1 failed in the real UI.
- **Tool.** Claude Code main agent (Opus 5.5) with Playwright; the fix by the `implementer`.
- **Context and key instruction.** The AC1 example from the specification, typed into the UI exactly as a user would, in the order a user would (add members **after** opening the group page).
- **AI diagnosis.** `ExpenseForm` stored the *included* members in a set initialised once at mount, so members added later were unchecked. The unit tests always mounted the form with the final member list. Suggested fix: store the *excluded* members, so new members are included by default; write the regression test first and record it failing on the faulty code.
- **Decision.** ✍️ Accepted. *(Author: why a browser run was worth it on top of the unit tests.)* The same stale-at-mount pattern was then found and fixed in the payment form's recipient default (Addendum 08c-A).
- **Verification.**
  - `frontend/src/components/Expenses.test.tsx` "ac1 equal split includes members added after the page loaded".
  - Faulty run `docs/evidence/08c-equal-split-regression-before.log` (exit 1, `participants: [1]`), fixed run `…-after.log` (exit 0).
  - Second browser run: balances `60.00 / -30.00 / -30.00`, screenshot `docs/evidence/e2e-group-page.png`.
- **Lesson / limitation.** Component tests with mocked `fetch` only cover the states the spec author imagined. A short end-to-end run along the acceptance criteria is cheap and found a real defect.

### Candidate 8: rejecting a lint rule workaround (stage 08)

- **Problem.** The first stage 08 gate failed on `react-hooks/set-state-in-effect` in `ExpenseForm.tsx` (loading the edited expense into state inside `useEffect`).
- **Options.** Disable the rule for the line; or restructure.
- **AI suggestion (main).** No `eslint-disable` (forbidden by `AGENTS.md`). Initialise the form state lazily from `editing` and remount the form with `key={editing ? `edit-${id}` : 'new'}`, which React recommends instead of syncing props into state (Addendum 08-B).
- **Decision.** ✍️ Accepted.
- **Verification.** Stage 08 receipt: `npm run lint` exit 0; "edit loads the expense and sends PUT" test passes.

## Dual implementation (D13)

*Stage 06. Not yet run.*

## Working methods (D14)

The settle-up panel (AC6 in the UI) was built twice from the same base commit `557ddf1` (stage 07):

- **Method 1, spec-driven:** main wrote `plan/08_frontend_expenses.md` (section 3.6 + tests); the `implementer` transcribed it as part of stage 08 on `main`.
- **Method 2, direct prompting:** a fresh agent got one conversational message quoting AC6 and the two endpoints, no spec; branch `compare/08-direct`, commit `827d2b3`.

Both were judged with the **same tests** (the spec's `SettleUpPanel.test.tsx`, 4 tests) and the same checklist.

| Criterion | Method 1: spec-driven | Method 2: direct prompting |
|-----------|----------------------|----------------------------|
| Shared tests, as written | 4/4 pass | 1/4 pass (`docs/evidence/d14-shared-tests.log`): button named `Record bob → alice`, not `Record` |
| Shared tests, button name relaxed to `/^Record/` | 4/4 | 4/4 (`docs/evidence/d14-relaxed-shared-tests.log`) |
| Own tests / lint / prettier / typecheck | pass | pass (32 tests) |
| Component interface | `{groupId, transfers}`: the page owns the balances query and passes data down | `{groupId}`: the panel fetches balances itself |
| Refresh after recording | invalidates expenses, payments and balances | refetches balances only; payments list (none in that version) would go stale |
| Disabled buttons while recording | yes | yes |
| Corrections needed | 0 for the panel (the 2 stage 08 addenda concerned other parts) | 0 |
| Wall clock | spec writing (main) + part of a ~8 min stage | ~1 min, one prompt |
| Fit with the rest of the app | consistent with the other stage 08 components | had to modify `GroupPage.test.tsx` routes on its own initiative |

**Evaluation.** ✍️ *(Author: confirm or reword.)* Direct prompting was much faster and produced correct, tested, accessible behaviour; on its own it is a perfectly good result. Its weak points appear only in context: the accessible names and the data flow were its own choices, so a test suite written independently (or a teammate's code) did not fit it without changes, and its local data fetching would need rework once payments and expenses share the page. The spec-driven method cost more up front but made the panel interchangeable and its tests reusable. For a small, isolated UI piece, direct prompting is enough; for parts that other components and tests depend on, the spec pays off.

**Limitations.** One feature, one run per method, and the direct prompt was written by the main agent who already knew the spec, which biases method 2 towards the intended design.

## Limitations of the method

- The implementer is only as good as the spec. Gaps in the spec went unasserted: see the stage 02 receipt, where dictionary order is not checked.
- The main agent's review compares the diff with the spec. A wrong spec passes review, so tests are the real check on correctness.
- Tests share the spec author's blind spots: the stage 08 component tests never added a member after the page loaded, so defect 08c passed all of them and was only caught by running the app (candidate 7).
- Agent sandboxes and command-rewriting hooks sometimes refused check commands inside subagents; the main agent's Tier 2 gate re-ran every check, so no result relies on a subagent's word alone.
