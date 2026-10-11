---
name: gate
description: Run the Tier 2 full gate for a stage (backend and/or frontend), capture logs and genuine exit codes, and append the acceptance receipt to the stage spec. Main agent only. Use when accepting a stage, e.g. "/gate 05" or "/gate 05 backend".
---

# Tier 2 gate

Arguments: `<stage number> [backend|frontend|all]`. The default scope is `all`.

Before you start: if the scope is narrower than `all`, write down why the other side's inputs are unchanged. For example: "frontend unchanged since stage 01: `git diff --stat <last-accepted-commit> -- frontend` is empty". Prove that with the `git diff` command itself.

## 1. Run

Run each command from the repo root, with the output redirected to its own log. Capture `$?` immediately after each command.

```
R=$(git rev-parse --show-toplevel); L="$R/.logs"; mkdir -p "$L"; N=<stage>

# backend (cd "$R/backend")
uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90 > "$L/$N-gate-pytest.log" 2>&1; e1=$?
uv run mypy                    > "$L/$N-gate-mypy.log" 2>&1;         e2=$?
uv run ruff check .            > "$L/$N-gate-ruff.log" 2>&1;         e3=$?
uv run ruff format --check .   > "$L/$N-gate-ruff-format.log" 2>&1;  e4=$?

# frontend (cd "$R/frontend")
npm run typecheck              > "$L/$N-gate-typecheck.log" 2>&1;    e5=$?
npm run lint                   > "$L/$N-gate-lint.log" 2>&1;         e6=$?
npm run test -- --run          > "$L/$N-gate-test.log" 2>&1;         e7=$?
npm run build                  > "$L/$N-gate-build.log" 2>&1;        e8=$?
```

Print every exit code in one line, for example `pytest=$e1 mypy=$e2 ...`.

## 2. Read

- From the pytest log, read the coverage table, the `TOTAL` line and the final summary line, including the warnings count. Count warnings with `grep -c Warning`; 0 is expected.
- From every other log, read the summary line.
- Never infer success from `grep` or `tail` alone. The exit code decides; the log supplies the numbers.

## 3. Decide

- Any non-zero exit means the stage is **not accepted**. Report the failing command, its exit code and the first decisive error line. Then write an Addendum to the spec, as described in `AGENTS.md` under "Implementation loop". Do not fix the code yourself.
- If every exit is 0, append the receipt below to `plan/NN_<slug>.md`. Then:
  - set the frontmatter to `status: accepted`, `completion_date: <today>` and `implementation_notes`;
  - update the `plan/00_index.md` row and `plan/WHATS_NEXT.md`;
  - add any decision-case candidates from this stage to `docs/AI_USAGE.md` (D15).

## Receipt template

```
## Acceptance receipt (YYYY-MM-DD)

Main reviewed the diff against sections 2–6: <match / findings>. Implementer Tier 1: <final exits; any mechanical fixes>. Tier 2 gate (`/gate NN <scope>`), logs in `.logs/NN-gate-*.log`:

| Step | Command | Exit | Summary |
|------|---------|------|---------|
| ... | ... | ... | ... |

**Accepted deviations:** ...
**Findings / follow-ups:** ...
```

Never commit as part of this skill. Committing needs separate user authorization.
