# AI usage

> **Living document.** It is updated at every stage acceptance (`plan/PLAN.md` D15). Sections marked ✍️ must be written or confirmed by the author in their own words before submission.

## Tools and models

| Tool | Model | Role |
|------|-------|------|
| Claude Code (CLI) | Claude Opus 5.5 | **Main agent:** requirements analysis, architecture decisions, stage specs, code review, and the Tier 2 gate. It writes no application code (`AGENTS.md`). |
| Claude Code `implementer` subagent (`.claude/agents/implementer.md`) | Claude Haiku (low effort) | **Implementer:** transcribes one resolved stage spec into code and tests, then runs the focused checks. |
| Google Antigravity | Gemini | The second implementation of stage 06, for the dual-tool comparison (planned, D13). |

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
| Implementation | stages 01–04 (`plan/0[1-4]_*.md`), commits `9b9c47e`…`94df2e5` |
| Testing | the test lists in each spec's section 6; the receipts in each spec; `.logs/*-gate-*.log` |
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

## Dual implementation (D13)

*Stage 06. Not yet run.*

## Working methods (D14)

*Stage 08. Not yet run.*

## Limitations of the method

- The implementer is only as good as the spec. Gaps in the spec went unasserted: see the stage 02 receipt, where dictionary order is not checked.
- The main agent's review compares the diff with the spec. A wrong spec passes review, so tests are the real check on correctness.
