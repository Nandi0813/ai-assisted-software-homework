---
status: accepted
completion_date: 2026-10-11
implementation_notes: "Check 6 exposed a real defect (Alembic CLI could not import app); fixed via Addendum 05b-A with a before/after regression test. Accepted: literal | in the help recipe (markdown escape in spec); smoke snippet run under /bin/bash because set -m fails in zsh."
---

# 05b: Developer Makefile

## 1. Goal, non-goals

**Goal.** A root `Makefile` that gives one-command workflows:
- `make dev` starts the backend and frontend together, with hot reload. Ctrl-C stops both.
- Separate targets to install, test, lint, type-check, format, run the full check, migrate, reset the dev database, build and clean.
- `make help` lists them all.

This is the setup and test-execution entry point the README will document for the course deliverables.

**Non-goals:**
- No production deployment, Docker or CI.
- No change to application code, configs or the `gate` skill. The `gate` skill keeps its per-command logs; `make check` is a human convenience with the same commands, without logs.

**Environment facts** (checked by main): GNU Make **3.81** (no `.ONESHELL`, no `$(file ...)`), `/bin/bash` 3.2 (no `wait -n`), `curl` and `lsof` in `/usr/bin` and `/usr/sbin`. **The repo path contains spaces**, so never use `$(CURDIR)` or `$(MAKEFILE_LIST)` unquoted in shell commands; use relative paths.

## 2. Owned files

| File | Action |
|------|--------|
| `Makefile` (repo root) | create |

Existing commands it wraps:
- Backend `uv` commands as in `AGENTS.md`, under "Validation policy".
- Frontend npm scripts `dev`, `build`, `lint`, `typecheck`, `test`, `format` and `format:check` in `frontend/package.json`.
- The ASGI target `app.main:app` (`backend/app/main.py:38`).
- The Vite proxy `'/api' → 'http://127.0.0.1:8000'` in `frontend/vite.config.ts`.
- The Alembic CLI config `backend/alembic.ini`, with `sqlalchemy.url = sqlite:///./splitledger.db`.

No other file may change.

## 3. Definitions

### Header

```
SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND_HOST ?= 127.0.0.1
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173
DEV_DB := backend/splitledger.db
# Development-only secret, so tokens survive uvicorn auto-reloads. Never use outside local dev.
DEV_JWT_SECRET ?= dev-only-insecure-secret-0123456789abcdef
```

`.PHONY` lists every target in the table below.

### Targets

Every target line carries a `## <description>` comment, which `help` uses. Recipes run from the repo root. Wherever a recipe enters a directory, it uses `cd backend && …` or `cd frontend && …` on the same logical line.

| Target | Prerequisites | `## ` description | Recipe |
|--------|---------------|-------------------|--------|
| `help` | — | `Show this help` | `@grep -E '^[a-zA-Z0-9_-]+:.*## ' Makefile \| awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'` |
| `install` | `install-backend install-frontend` | `Install backend and frontend dependencies` | — |
| `install-backend` | — | `Sync backend virtualenv (uv)` | `cd backend && uv sync` |
| `install-frontend` | — | `Install frontend packages from the lockfile (npm ci)` | `cd frontend && npm ci` |
| `frontend/node_modules/.package-lock.json` | `frontend/package-lock.json` | *(no `##`; file target)* | `cd frontend && npm ci` |
| `dev` | `frontend/node_modules/.package-lock.json` | `Run backend (:8000) and frontend (:5173) with reload; Ctrl-C stops both` | see "dev recipe" below |
| `dev-backend` | — | `Run only the backend with reload` | `cd backend && SPLITLEDGER_JWT_SECRET='$(DEV_JWT_SECRET)' uv run uvicorn app.main:app --reload --reload-dir app --host $(BACKEND_HOST) --port $(BACKEND_PORT)` |
| `dev-frontend` | `frontend/node_modules/.package-lock.json` | `Run only the frontend dev server` | `cd frontend && npm run dev -- --host 127.0.0.1 --port $(FRONTEND_PORT) --strictPort` |
| `test` | `test-backend test-frontend` | `Run all tests` | — |
| `test-backend` | — | `Run backend tests` | `cd backend && uv run pytest -q` |
| `test-frontend` | `frontend/node_modules/.package-lock.json` | `Run frontend tests` | `cd frontend && npm run test -- --run` |
| `lint` | `frontend/node_modules/.package-lock.json` | `Lint and format-check both sides (no changes)` | four lines: `cd backend && uv run ruff check .`; `cd backend && uv run ruff format --check .`; `cd frontend && npm run lint`; `cd frontend && npm run format:check` |
| `typecheck` | `frontend/node_modules/.package-lock.json` | `Type-check both sides` | two lines: `cd backend && uv run mypy`; `cd frontend && npm run typecheck` |
| `format` | `frontend/node_modules/.package-lock.json` | `Auto-format both sides (writes files)` | three lines: `cd backend && uv run ruff check --fix .`; `cd backend && uv run ruff format .`; `cd frontend && npm run format` |
| `check` | `frontend/node_modules/.package-lock.json` | `Full quality gate (coverage >= 90%, types, lint, tests, build)` | eight lines, in this order: `cd backend && uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90`; `cd backend && uv run mypy`; `cd backend && uv run ruff check .`; `cd backend && uv run ruff format --check .`; `cd frontend && npm run typecheck`; `cd frontend && npm run lint`; `cd frontend && npm run test -- --run`; `cd frontend && npm run build` |
| `migrate` | — | `Apply database migrations to the dev database` | `cd backend && uv run alembic upgrade head` |
| `reset-db` | — | `Delete the dev database and re-create it empty (DESTROYS dev data)` | two lines: `rm -f "$(DEV_DB)"`; `$(MAKE) migrate` |
| `build` | `frontend/node_modules/.package-lock.json` | `Build the frontend for production` | `cd frontend && npm run build` |
| `clean` | — | `Remove caches, coverage and build output (keeps deps and dev DB)` | `rm -rf backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache backend/.coverage backend/htmlcov frontend/dist frontend/coverage .logs` |
| `distclean` | `clean` | `Also remove installed dependencies (.venv, node_modules)` | `rm -rf backend/.venv frontend/node_modules` |

In the `lint`, `typecheck`, `format` and `check` targets, each listed line is its own recipe line, so Make stops at the first failure.

### `dev` recipe

This is a single logical recipe line, joined with ` \` continuations:

1. `trap 'kill 0' INT TERM;`
2. `( $(MAKE) --no-print-directory dev-backend ) &`
3. `( $(MAKE) --no-print-directory dev-frontend ) &`
4. `wait`

The prerequisite runs `npm ci` only when `frontend/package-lock.json` is newer than `node_modules/.package-lock.json`, or when `node_modules` is missing. The backend needs no prerequisite, because `uv run` syncs automatically.

## 4. Edit recipe, in order

1. Create `Makefile` at the repo root with the header, the `.PHONY` line and the targets in table order, then the `dev` recipe from section 3.
2. Recipe lines must start with a literal TAB character.
3. Run the section 6 checks.

## 5. Edge cases

| Situation | Expected |
|-----------|----------|
| `make` with no target | prints the help list, exit 0 |
| `make dev`, then Ctrl-C | both servers stop; ports 8000 and 5173 are free afterwards |
| `make dev` on a fresh clone (no `node_modules`) | `npm ci` runs once, then both servers start |
| `make dev` a second time | no `npm ci` (lockfile unchanged) |
| `make reset-db` with no DB file | `rm -f` succeeds; the migration creates `backend/splitledger.db` |
| `make lint` with a ruff violation | stops at that line with a non-zero exit |
| Repo path with spaces | every target works (the path contains `AI Assisted Software`) |

## 6. Checks (Tier 1)

Run from the repo root and report each genuine exit code. Create `.logs/` first (`mkdir -p .logs`); it is gitignored.

1. `make > .logs/05b-help.log 2>&1; echo $?`: exit 0. The log must list all 19 `##` targets (every row of the table except the file target).
2. `make test > .logs/05b-test.log 2>&1; echo $?`: exit 0.
3. `make lint > .logs/05b-lint.log 2>&1; echo $?`: exit 0.
4. `make typecheck > .logs/05b-typecheck.log 2>&1; echo $?`: exit 0.
5. `make check > .logs/05b-check.log 2>&1; echo $?`: exit 0. The log contains `Required test coverage of 90% reached`.
6. `make reset-db > .logs/05b-reset.log 2>&1; echo $?`: exit 0. Then `test -f backend/splitledger.db; echo $?` gives 0. Then `cd backend && sqlite3 splitledger.db "SELECT version_num FROM alembic_version"` prints `0002`. This also exercises the CLI branch of `backend/app/migrations/env.py` for the first time.
7. `make dev` smoke test. Run exactly this bash snippet from the repo root and report each echoed value:
   ```
   set -m
   make dev > .logs/05b-dev.log 2>&1 &
   DEV=$!
   for i in $(seq 1 40); do curl -sf http://127.0.0.1:5173/api/health >/dev/null && break; sleep 1; done
   curl -sf http://127.0.0.1:8000/api/health; echo " direct=$?"
   curl -sf http://127.0.0.1:5173/api/health; echo " proxy=$?"
   curl -sf -o /dev/null http://127.0.0.1:5173/; echo " index=$?"
   kill -INT -- -$DEV; wait $DEV; echo "make-exit=$?"
   sleep 2
   lsof -ti tcp:8000; echo "port8000-free=$?"
   lsof -ti tcp:5173; echo "port5173-free=$?"
   ```
   Expected:
   - `{"status":"ok"} direct=0`
   - `{"status":"ok"} proxy=0`
   - `index=0`
   - `port8000-free=1` and `port5173-free=1` (`lsof` exits 1 when nothing listens)
   - `make-exit` may be any value; report it.
8. `git status --short` shows only `?? Makefile` (plus main-owned `plan/` edits). `backend/splitledger.db` must not appear, because it is gitignored via `*.db`.

## 7. Stop conditions

Stop and report; do not work around:
- Any check in section 6 fails. Paste the decisive log lines.
- After the smoke test either port is still busy. Report the `lsof -ti` PIDs; do not kill them with any method other than the snippet's.
- A needed change outside `Makefile`, or a Make feature newer than 3.81.
- `make help` misaligns or misses a target. That is mechanical, so fix the `##` comment and re-run; it is not a stop.

Done when: all section 6 checks give the expected results and the report is delivered.

## Addendum 05b-A (a real defect found by check 6)

**Cause.** `cd backend && uv run alembic upgrade head` fails with `ModuleNotFoundError: No module named 'app'` at `backend/app/migrations/env.py:6`.
- The Alembic CLI does not put the backend directory on `sys.path`.
- pytest never noticed, because `pythonpath = ["."]` adds it inside the test process only.
- The CLI branch of `env.py` had never run before this check.

**Fix.** Use Alembic's documented `prepend_sys_path` option. Use `%(here)s`, the directory of `alembic.ini`, rather than `.`, so the fix works from any working directory. Add `path_separator = os` so that the repo path, which contains spaces, is not split, and so that Alembic 1.20 does not warn "No path_separator found in configuration".

**Owned files (added):** `backend/alembic.ini` and `backend/tests/test_migrations.py`, plus `Makefile` (help width).

**Recipe, in order.** The order matters: it produces before and after evidence for the faulty-vs-fixed testing requirement.

1. **Write the regression test first.** In `backend/tests/test_migrations.py`, add these imports: `os`, `subprocess`, `sys`.

   Add a module constant `BACKEND_DIR = Path(__file__).resolve().parents[1]`.

   Add **`test_alembic_cli_upgrade_runs_outside_pytest_path(tmp_path: Path) -> None`**:
   1. `env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}`.
   2. `result = subprocess.run([sys.executable, "-m", "alembic", "-c", str(BACKEND_DIR / "alembic.ini"), "upgrade", "head"], cwd=tmp_path, env=env, capture_output=True, text=True, check=False)`.
   3. `assert result.returncode == 0, result.stderr`.
   4. `assert (tmp_path / "splitledger.db").exists()`. `sqlalchemy.url` is relative to the working directory, so the database lands in `tmp_path`.
2. **Before the fix**, in `backend/`, run `uv run pytest tests/test_migrations.py::test_alembic_cli_upgrade_runs_outside_pytest_path -q > "../.logs/05b-A-regression-before.log" 2>&1; echo $?`. **Expected: exit 1**, and the log contains `ModuleNotFoundError: No module named 'app'`. If it passes instead, stop and report.
3. **Apply the fix.** In `backend/alembic.ini`, under `[alembic]` and after `script_location`, add two lines in this order:
   - `prepend_sys_path = %(here)s`
   - `path_separator = os`

   Change nothing else.
4. **After the fix**, run the same command with the output going to `../.logs/05b-A-regression-after.log`. **Expected: exit 0**, with 1 passed.
5. **Fix the help width.** In `Makefile`, change the help `printf` width from `%-16s` to `%-18s`. The longest target, `install-frontend`, is 16 characters.
6. **Re-run.** Run section 6 checks 6, 7 and 8 exactly as written, then `cd backend && uv run pytest tests -q`, `uv run ruff check tests/test_migrations.py`, `uv run ruff format --check tests/test_migrations.py` and `uv run mypy`.

**Stop if:**
- step 2 passes;
- step 4 fails;
- the Alembic output contains `path_separator`;
- any check 6, 7 or 8 result differs from section 6.

Report both regression logs' last 5 lines.

## Acceptance receipt (2026-10-11)

**Review.** Main reviewed the `Makefile`, `backend/alembic.ini` and `backend/tests/test_migrations.py` diffs against section 3 and Addendum 05b-A. They match.

**Implementer checks.** Section 6 checks 1–8, re-run after 05b-A, gave these results:
- `make`, `make test`, `make lint`, `make typecheck` and `make check` all exited 0.
- `make reset-db` exited 0, and `alembic_version` = `0002`.
- The smoke test printed `direct=0`, `proxy=0` and `index=0`, and afterwards `port8000-free=1` and `port5173-free=1`.
- `make-exit=143` is the SIGTERM from `trap 'kill 0'`, which the spec allows.

**Defect evidence** (sanitized copies, committed):
- `docs/evidence/05b-alembic-cli-regression-before.log`: exit 1, `ModuleNotFoundError: No module named 'app'`.
- `docs/evidence/05b-alembic-cli-regression-after.log`: exit 0, `1 passed`.

**Tier 2 gate** (`/gate 05b backend`). Logs are in `.logs/05b-gate-*.log`. The frontend is unchanged since `9943c99` (empty diff).

| Step | Command | Exit | Summary |
|------|---------|------|---------|
| backend tests | `uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90` | 0 | 175 passed, 0 warnings; coverage 100.00% (491 stmts, 88 branches) |
| backend types | `uv run mypy` | 0 | no issues in 31 source files |
| backend lint | `uv run ruff check .` | 0 | All checks passed |
| backend format | `uv run ruff format --check .` | 0 | 31 files already formatted |

**Accepted deviations:**
- A literal `|` in the `help` recipe. The `\|` in section 3 was Markdown table escaping.
- The smoke snippet was run under `/bin/bash`. The implementer's shell is zsh, where `set -m` fails; that was a spec error by main.

**Findings and follow-ups:**
- `make reset-db` deletes the database before migrating, so a failing migration leaves no dev database. This is accepted for a dev-only reset target.
- Any future smoke snippets in specs must say "run with `/bin/bash`".
