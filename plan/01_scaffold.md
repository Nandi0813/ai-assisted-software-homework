---
status: accepted
completion_date: 2026-10-11
implementation_notes: "No deviations. Known warning: StarletteDeprecationWarning (httpx with starlette.testclient; suggests httpx2), deferred to stage 04."
---

# 01: Scaffold `backend/` and `frontend/`

## 1. Goal, non-goals

**Goal.** Create two runnable app skeletons, the Python backend in `backend/` and the React frontend in `frontend/`, each with its tooling configured. Every Tier 2 gate command in `AGENTS.md` must exit 0 when this stage is done.

**Non-goals:**
- No database, auth, domain logic or business endpoints.
- No routing, TanStack Query or styling in the frontend.
- No CI.
- No dependencies beyond those listed here (stages 02+ add their own).
- No edits to `docs/`, `plan/`, `AGENTS.md`, `.claude/`, the root `.gitignore` or the root `README.md`.

## 2. Owned files

All paths are relative to the repo root.

**Moved with `git mv`, content preserved except as edited below:**
- `pyproject.toml` → `backend/pyproject.toml`
- `uv.lock` → `backend/uv.lock`
- `.python-version` → `backend/.python-version`

**Created, backend:**
- `backend/app/__init__.py`: empty.
- `backend/app/main.py`: defines `create_app` and `app`.
- `backend/app/api/__init__.py`: empty.
- `backend/app/api/health.py`: defines `router`, `HealthResponse` and `get_health`.
- `backend/tests/conftest.py`: defines the `client` fixture.
- `backend/tests/test_health.py`: two tests.

**Created, frontend.** The generator creates these, and they are then edited as described below:
- `frontend/` contains the files from `create-vite@9.2.1` (template `react-ts`, with ESLint).
- Added: `frontend/src/test/setup.ts`, `frontend/src/App.test.tsx`, `frontend/.prettierrc.json` and `frontend/.prettierignore`.

**Deleted from the generated output:**
- `frontend/README.md`
- `frontend/public/icons.svg`
- `frontend/src/App.css`
- `frontend/src/index.css`
- `frontend/src/assets/` (the whole directory)

No existing helpers to reuse; the repo has no code yet. There are no callers yet.

## 3. Signatures, types, behavior

### Backend

`backend/app/api/health.py`:
- `class HealthResponse(pydantic.BaseModel)` with a single field `status: Literal["ok"]`.
- `router = APIRouter(tags=["health"])`.
- `def get_health() -> HealthResponse`, registered as `GET /health` on `router` with `response_model=HealthResponse`. It returns `HealthResponse(status="ok")`. It has no parameters and never raises.

`backend/app/main.py`:
- `def create_app() -> FastAPI` builds `FastAPI(title="SplitLedger API", version="0.1.0")`. It includes `app.api.health.router` with `prefix="/api"` and returns the app. Each call returns a new instance.
- Module level: `app = create_app()`. The ASGI target is `app.main:app`.

`backend/tests/conftest.py`:
- Fixture `client() -> Iterator[TestClient]` (`Iterator` from `collections.abc`). It enters `TestClient(create_app())` as a context manager and yields the client.

### Frontend

- `App` is a default-export function component with no props. It renders a `<main>` element containing:
  - an `<h1>` with the text `SplitLedger`;
  - a `<p>` with the text `Group expense splitting`.
  - It has no state, no imports of CSS or assets, and no other markup.
- `src/main.tsx` stays as generated, except that the `import './index.css'` line is removed.

## 4. Edit recipe, in order

Run from the repo root unless a step says otherwise. Stop at the first failure (see section 7).

1. **Move the backend project files.** `mkdir backend`, then `git mv pyproject.toml uv.lock .python-version backend/`.
2. **Edit the `[project]` table in `backend/pyproject.toml`:**
   - Delete the `readme = "README.md"` line.
   - Set `description = "SplitLedger backend API (FastAPI)"`.
   - Keep `name = "splitledger"`, `version` and `requires-python` unchanged.
3. **Add dependencies.** In `backend/`, run `uv add fastapi uvicorn`, then `uv add --dev pytest pytest-cov httpx ruff mypy`. Accept the versions uv resolves; the lockfile pins them.
4. **Append tool configuration to `backend/pyproject.toml`**, exactly these keys and values:

   | Table | Key | Value |
   |-------|-----|-------|
   | `[tool.pytest.ini_options]` | `testpaths` | `["tests"]` |
   | | `pythonpath` | `["."]` |
   | | `addopts` | `"-ra --strict-markers --strict-config"` |
   | `[tool.coverage.run]` | `branch` | `true` |
   | | `source` | `["app"]` |
   | `[tool.coverage.report]` | `show_missing` | `true` |
   | `[tool.mypy]` | `strict` | `true` |
   | | `python_version` | `"3.14"` |
   | | `files` | `["app", "tests"]` |
   | | `plugins` | `["pydantic.mypy"]` |
   | `[tool.ruff]` | `line-length` | `100` |
   | | `target-version` | `"py314"` |
   | `[tool.ruff.lint]` | `select` | `["E", "F", "W", "I", "B", "UP", "SIM", "RUF", "N", "PT"]` |

5. **Create the backend source files** from section 3:
   - `backend/app/__init__.py` and `backend/app/api/__init__.py` are empty.
   - In `health.py`, import `Literal` from `typing`, `APIRouter` from `fastapi` and `BaseModel` from `pydantic`.
6. **Create the backend tests** from section 6.
7. **Generate the frontend.** From the repo root, run `npx -y create-vite@9.2.1 frontend --template react-ts --eslint --no-immediate --no-interactive`. Expected generated files:
   - `.gitignore`, `README.md`, `eslint.config.js`, `index.html`, `package.json`
   - `public/favicon.svg`, `public/icons.svg`
   - `src/App.css`, `src/App.tsx`, `src/assets/{hero.png,react.svg,vite.svg}`, `src/index.css`, `src/main.tsx`
   - `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `vite.config.ts`
8. **Install dependencies.** In `frontend/`, run `npm install`, then:
   `npm install -D vitest@^5.0.3 jsdom@^29.1.1 @testing-library/react@^16.3.3 @testing-library/dom@^10.4.2 @testing-library/jest-dom@^7.0.1 prettier@^3.9.10 eslint-config-prettier@^10.1.8`
9. **Delete the template files** listed in section 2.
10. **Edit `frontend/package.json`:**
    - Set `"name": "splitledger-frontend"`.
    - Add these scripts and keep the generated `dev`, `build`, `lint` and `preview` scripts unchanged:
      - `"typecheck": "tsc -b"`
      - `"test": "vitest"`
      - `"format": "prettier --write ."`
      - `"format:check": "prettier --check ."`
11. **Edit `frontend/index.html`:** set `<title>` to `SplitLedger`. Change nothing else.
12. **Edit `frontend/tsconfig.app.json`:** in `compilerOptions`, add `"strict": true` under the `/* Linting */` group. Leave `types` as `["vite/client"]`; tests import from `vitest` explicitly, so no globals are needed.
13. **Edit `frontend/vite.config.ts`:**
    - Import `defineConfig` from `vitest/config` instead of `vite`. Keep the `react()` plugin.
    - Add `server.proxy` with the key `'/api'` and the target `'http://127.0.0.1:8000'`.
    - Add a `test` block:
      - `environment: 'jsdom'`
      - `setupFiles: ['./src/test/setup.ts']`
      - `include: ['src/**/*.test.{ts,tsx}']`
14. **Create `frontend/src/test/setup.ts`.** It imports `@testing-library/jest-dom/vitest` for side effects, imports `afterEach` from `vitest` and `cleanup` from `@testing-library/react`, and registers `afterEach(cleanup)`.
15. **Replace the whole body of `frontend/src/App.tsx`** with the component from section 3. Remove the `import './index.css'` line from `src/main.tsx`.
16. **Edit `frontend/eslint.config.js`:**
    - Add `'coverage'` to the `globalIgnores` array.
    - Import `eslintConfigPrettier` from `eslint-config-prettier/flat` and append it as the last element of the `defineConfig([...])` array.
17. **Create `frontend/.prettierrc.json`:** `{"semi": false, "singleQuote": true}`.
18. **Create `frontend/.prettierignore`** with the lines `dist`, `coverage` and `package-lock.json`.
19. **Create the frontend test** from section 6.
20. **Format.** In `frontend/`, run `npx prettier --write .` once. This is a mechanical change and is allowed.

## 5. Edge cases

| Input | Expected |
|-------|----------|
| `GET /api/health` | 200, body exactly `{"status": "ok"}` |
| `GET /health` (no `/api` prefix) | 404 |
| `create_app()` called twice | two distinct `FastAPI` objects (`is not`) |

## 6. Tests

`backend/tests/test_health.py`:
- **`test_health_returns_ok(client: TestClient) -> None`**
  - Action: `client.get("/api/health")`.
  - Assert `status_code == 200` and `.json() == {"status": "ok"}`.
- **`test_health_requires_api_prefix(client: TestClient) -> None`**
  - Action: `client.get("/health")`.
  - Assert `status_code == 404`.

`frontend/src/App.test.tsx`:
- Import `describe`, `it` and `expect` from `vitest`, and `render` and `screen` from `@testing-library/react`.
- **`describe('App')`, test `it('renders the app title')`**
  - Action: `render(<App />)`.
  - Assert `screen.getByRole('heading', { level: 1, name: 'SplitLedger' })` is in the document (`toBeInTheDocument()`).

### Focused checks (Tier 1)

Run each one and report its exit code.

In `backend/`:
- `uv run pytest tests/test_health.py -q`
- `uv run ruff check app tests`
- `uv run ruff format --check app tests`
- `uv run mypy`

In `frontend/`:
- `npm run test -- --run src/App.test.tsx`
- `npm run lint`
- `npm run format:check`
- `npm run typecheck`
- `npm run build`

The full suite and the whole-project lint are the same as the focused checks at this stage, and they are expected here. Coverage is not run (main runs it in Tier 2).

## 7. Stop conditions

Stop and report; do not work around:
- `create-vite` prompts interactively, or generates a file set different from step 7.
- `uv add` or `npm install` fails, or prints a peer-dependency conflict (`ERESOLVE`).
- Any check in section 6 exits non-zero after one mechanical fix attempt (formatting, imports, syntax only).
- A tool rejects a config key from step 4, 13 or 16.
- Any step needs a file not listed in section 2.

Done when: every step is completed, all section 6 checks exit 0, and the report lists the changed files and the exit codes.

## Acceptance receipt (2026-10-11)

Main reviewed the full diff against sections 2–6: it matches the spec, with no extra files or dependencies.

The implementer's Tier 1 checks all exited 0. Main then ran the Tier 2 gate. Logs are in `.logs/01-gate-*.log`.

| Step | Command | Exit | Summary |
|------|---------|------|---------|
| backend tests | `uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90` | 0 | 2 passed, 1 warning; coverage 100.00% (15 stmts, 0 branches) |
| backend types | `uv run mypy` | 0 | no issues in 6 source files |
| backend lint | `uv run ruff check .` | 0 | All checks passed |
| backend format | `uv run ruff format --check .` | 0 | 6 files already formatted |
| frontend types | `npm run typecheck` | 0 | — |
| frontend lint | `npm run lint` | 0 | — |
| frontend tests | `npm run test -- --run` | 0 | 1 file, 1 test passed |
| frontend build | `npm run build` | 0 | `dist/assets/index-*.js` 219.64 kB |

**Accepted deviations:** none.

**Known warnings, not failures:**
- `StarletteDeprecationWarning`: `httpx` with `starlette.testclient` is deprecated, and Starlette suggests `httpx2`. This is deferred to stage 04, which adds more dependencies anyway.
- `uv`: "`VIRTUAL_ENV=.../hw/.venv` does not match the project environment path". The user's shell or IDE still points at the stale root `.venv`, while the project environment is now `backend/.venv`.
