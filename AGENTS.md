# AGENTS.md

Workflow authority for every AI agent working in this repository (SplitLedger: FastAPI + React expense splitter).

## Communication

- Terse and technically exact. No filler, greetings, recaps or closers.
- Code, commands, paths, error messages and commit messages are quoted verbatim, never paraphrased.
- Report facts with evidence: the command run, its genuine exit code, the relevant output line.

## Authority and startup

- `plan/PLAN.md` is the architecture authority. The user's current instructions override it; when they do, main records the change in `PLAN.md`.
- At startup:
  1. Run `git status --short` and `git log -1`. Preserve all dirty work; never discard or overwrite it.
  2. Read only: `plan/HANDOFF.md` (if present), `plan/WHATS_NEXT.md`, the relevant rows of `plan/00_index.md`, and the active stage spec.
  3. Never read every plan or archived spec. Open other specs only when the active one references them.
- Run no startup baseline tests. Trust accepted receipts whose inputs have not changed since acceptance.

## Roles

### Main (planner/reviewer)

- The sole planner and reviewer. Main investigates, designs, writes plans, reviews diffs, runs the final gate and tracks status.
- Main MUST NOT write or edit any application code, tests, config, generated code or probe code: not even one line, and not via scripts, formatters or autofix (`ruff --fix`, `eslint --fix`, `prettier --write`, `sed`, codegen).
- Main may edit: plans (`plan/`), receipts, docs (`docs/`, `README.md`), and workflow/agent settings (`AGENTS.md`, `CLAUDE.md`, `.claude/`).
- Plans and messages contain prose, signatures, data definitions and non-executable pseudocode, never ready-to-apply patches.

### Implementer (writer)

- Only transcribes main's resolved plan into code. It has no design authority over algorithms, APIs, defaults, error policies, abstractions, dependencies, test cases or scope.
- Missing decisions, contradictions or unexpected failures go back to main. The implementer never resolves them itself.

## Required plan before delegation

Each stage has a spec at `plan/NN_<slug>.md` with frontmatter:

```yaml
---
status: planned | in_progress | accepted | blocked
completion_date: null        # YYYY-MM-DD once accepted
implementation_notes: ""     # deviations accepted at review
---
```

The spec must contain:

1. Goal, non-goals, and cause (for bugs).
2. Exact owned files and symbols, their callers, and helpers to reuse with their locations (`path:line`).
3. Exact signatures, types, defaults and error behavior.
4. An ordered per-file edit recipe with control flow.
5. Edge cases with concrete inputs and expected outputs.
6. Exact tests (setup, actions, assertions), plus focused test selectors and static-check commands.
7. Stop conditions.

No TBDs, no "handle edge cases", no choices left to the worker. If main cannot fill a section, it keeps investigating read-only until it can.

## Implementation loop

- Spawn one writer per stage: Agent with `subagent_type="implementer"`. Never a fork, never a model override. Use a fresh implementer for each stage; send corrections to the same implementer via SendMessage.
- The assignment is self-contained: spec path, owned files, checks, stop conditions. It names the files the implementer may touch; the implementer must preserve everyone else's edits.
- The implementer runs only the focused checks named in the spec and reports: changed files, commands, genuine exit codes, results, log paths, deviations and hazards.
- On a gap, main appends `Addendum NNx-A`, `NNx-B`, ... to the spec with a resolved recipe, then sends it to the same implementer. Never escalate model or effort; make the plan clearer instead.
- Main reviews the full diff against the spec, then runs one final Tier 2 gate.
- After acceptance, main appends an acceptance receipt to the spec (commands, exit codes, test and coverage totals, accepted deviations), then updates the spec frontmatter, the `plan/00_index.md` row and `plan/WHATS_NEXT.md`.
- Commit only when the user authorizes it, staging exact paths. Never `git add .` or `git add -A`, never push, never use a destructive reset (`git reset --hard`, `git checkout -- .`, `git clean`).

## Waiting

- Event-driven. Main never does delegated work while a worker runs.
- No polling and no "status?" messages to a running worker. Wait for its completion notification.

## Validation policy

### Tier 1: implementer, per change

Focused tests on the affected modules, plus targeted lint, format and type checks on the changed files. No coverage, no full suite.

| Side | Focused tests | Lint / format | Types |
|------|---------------|---------------|-------|
| Backend (run in `backend/`) | `uv run pytest <test_file>::<test_name> -q` | `uv run ruff check <files>` and `uv run ruff format --check <files>` | `uv run mypy <files>` |
| Frontend (run in `frontend/`) | `npm run test -- --run <test_file>` | `npx eslint <files>` and `npx prettier --check <files>` | `npm run typecheck` |

### Tier 2: main only, once per stable batch

The full gate. Redirect each command's output to `.logs/<stage>-<step>.log`, then read the real exit code (`echo $?` captured immediately) and the summary in the log. Never infer success from `grep` or `tail` alone.

```
# backend/
uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90
uv run mypy
uv run ruff check .
uv run ruff format --check .

# frontend/
npm run typecheck
npm run lint
npm run test -- --run
npm run build
```

- Re-run only when an input changed. Edits to docs, plans or agent settings do not invalidate accepted product receipts.
- Slow checks: none yet. Any future end-to-end (browser) suite is Tier 2 only.
- Paid or live services: none. The app calls no external services; tests must never require network access.

> These commands become valid once stage 01 (scaffold) is accepted. Until then, no gate exists.

## Engineering invariants

> **Derived from the repository and `docs/SPECIFICATION.md`; confirmed by the user on 2026-10-11.**

- **Layout:** `backend/` is the Python 3.14 FastAPI app managed by uv; `frontend/` is React + Vite + TypeScript. Neither imports from the other; they share only the HTTP API.
- **Backend layers:** `api` (FastAPI routers, request/response schemas) → `services` (use cases, authorization) → `repositories` (SQLAlchemy, SQLite). `domain` holds pure business rules (splitting, rounding, balances, settle-up): no I/O, no FastAPI, no SQLAlchemy imports.
- **Money:** amounts are integer cents (`int`) everywhere inside the backend. `float` is forbidden for money. The API exchanges amounts as decimal strings with at most 2 decimal places (e.g. `"33.34"`).
- **Authorization:** a non-member accessing a group gets HTTP 404, never 403 (spec criterion 5).
- **Persistence:** schema changes go through Alembic migrations only. Existing data must survive every migration (needed for the change request).
- **Typing:** `mypy --strict` for the backend and `"strict": true` for TypeScript. No `Any`, `# type: ignore`, `as any` or `@ts-ignore` without an inline reason, and none in `domain`.
- **Lint:** Ruff (lint + format) for the backend; ESLint + Prettier for the frontend. No blanket `noqa` or `eslint-disable` comments.
- **Coverage:** backend line + branch coverage ≥ 90% on `backend/app`. The frontend is not coverage-gated.
- **Tests:** every acceptance criterion maps to at least one check, recorded in `docs/TESTING.md`. Automated tests for criterion N are named `test_acN_<behavior>`.
- **Forbidden:** bare `except:`, `print` debugging in committed code, secrets in the repo (use `.env`, which is gitignored), committing course materials or personal identifiers (Neptun code).
