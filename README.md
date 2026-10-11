# SplitLedger

A web app for splitting shared expenses in a group. Members record what they paid and who shared it, see who owes whom, and settle up with at most n−1 transfers.

Individual homework project for the *AI Assisted Software Development* MSc course (2026).

> **Status:** in development.
> - Done: the backend domain rules, persistence, authentication and the groups API.
> - Next: the expenses and payments API, then the UI. Until the UI lands, use the interactive API docs (see [First steps](#first-steps)).
>
> Progress: [plan/00_index.md](plan/00_index.md).

## Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Configuration](#configuration)
4. [Running the app](#running-the-app)
5. [First steps](#first-steps)
6. [Testing and quality checks](#testing-and-quality-checks)
7. [Database](#database)
8. [All `make` commands](#all-make-commands)
9. [Project structure](#project-structure)
10. [Documentation](#documentation)

## Prerequisites

| Tool | Version | Check | Install |
|------|---------|-------|---------|
| Python | 3.14 | `python3 --version` | installed automatically by uv |
| [uv](https://docs.astral.sh/uv/) | 0.10 or newer | `uv --version` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js | 20.19+ or 22.12+ (developed on 24) | `node --version` | [nodejs.org](https://nodejs.org/) |
| npm | comes with Node.js | `npm --version` | — |
| GNU Make | 3.81 or newer | `make --version` | preinstalled on macOS and most Linux distributions |

The app runs on macOS and Linux. On Windows, use WSL.

## Installation

```bash
git clone https://github.com/Nandi0813/ai-assisted-software-homework.git
cd ai-assisted-software-homework
make install
```

`make install` does two things:
- runs `uv sync` in `backend/`, which creates `backend/.venv` and downloads Python 3.14 if needed;
- runs `npm ci` in `frontend/`.

## Configuration

No configuration is needed for local development. The backend reads these optional environment variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `SPLITLEDGER_DATABASE_URL` | `sqlite:///./splitledger.db` (relative to `backend/`) | SQLite database location. Only SQLite is supported. |
| `SPLITLEDGER_JWT_SECRET` | a random value on every start | The secret used to sign login tokens. `make dev` sets a fixed **development-only** value, so you stay logged in when the backend reloads. Always set your own secret outside local development. |
| `SPLITLEDGER_ACCESS_TOKEN_MINUTES` | `60` | How long a login token stays valid. |

## Running the app

```bash
make dev
```

This starts both servers with hot reload. Press **Ctrl-C** to stop both.

| What | URL |
|------|-----|
| Web app (frontend) | http://127.0.0.1:5173 |
| API | http://127.0.0.1:8000/api |
| Interactive API docs (Swagger UI) | http://127.0.0.1:8000/docs |

- The frontend forwards `/api/*` requests to the backend, so the browser only talks to port 5173.
- Database migrations run automatically when the backend starts. On first start this creates `backend/splitledger.db`.
- To run one side only, use `make dev-backend` or `make dev-frontend`.

## First steps

Try the API in Swagger UI at http://127.0.0.1:8000/docs:

1. `POST /api/auth/register` with `{"username": "alice", "password": "correct-horse"}`.
2. Click **Authorize** and log in as `alice` / `correct-horse`.
3. `POST /api/groups` with `{"name": "Trip"}`.
4. Register a second user, `bob`, then `POST /api/groups/1/members` with `{"username": "bob"}`.
5. `GET /api/groups/1` lists both members in the order they joined.

## Testing and quality checks

| Command | What it runs |
|---------|--------------|
| `make test` | All backend (pytest) and frontend (Vitest) tests |
| `make test-backend` / `make test-frontend` | One side only |
| `make lint` | Ruff, ESLint and Prettier in check mode (changes nothing) |
| `make typecheck` | mypy (strict) and the TypeScript compiler |
| `make format` | Auto-formats both sides (**writes files**) |
| `make check` | The full quality gate: tests with backend coverage of at least 90%, type checks, lint, format check and production build |

A table mapping each acceptance criterion to the checks that verify it will be added as `docs/TESTING.md` in stage 09.

## Database

| Command | Effect |
|---------|--------|
| `make migrate` | Applies pending migrations to `backend/splitledger.db` |
| `make reset-db` | **Deletes** the dev database and re-creates it empty |

Migrations live in `backend/app/migrations/versions/`. Every migration is tested for upgrade, downgrade and preservation of existing data.

## All `make` commands

Run `make` (or `make help`) to list every target with a short description.

| Target | Purpose |
|--------|---------|
| `install`, `install-backend`, `install-frontend` | Install dependencies |
| `dev`, `dev-backend`, `dev-frontend` | Run with hot reload |
| `test`, `test-backend`, `test-frontend` | Run tests |
| `lint`, `typecheck`, `format`, `check` | Quality checks |
| `migrate`, `reset-db` | Database |
| `build` | Production build of the frontend (`frontend/dist`) |
| `clean` | Remove caches, coverage and build output |
| `distclean` | `clean`, plus remove `backend/.venv` and `frontend/node_modules` |

## Project structure

```
backend/            FastAPI app (Python 3.14, uv)
  app/api/          HTTP routers and request/response schemas
  app/services/     Use cases and authorization
  app/repositories/ SQLAlchemy models and queries
  app/domain/       Pure business rules: money, splits, balances, settle-up
  app/migrations/   Alembic migrations
  tests/            pytest suite
frontend/           React + Vite + TypeScript app
docs/               Specification, AI usage, testing evidence
plan/               Architecture decisions and stage specs, with acceptance receipts
AGENTS.md           Rules for the AI agents working in this repo
Makefile            Developer commands
```

## Documentation

- [Specification and acceptance criteria](docs/SPECIFICATION.md)
- [AI usage and decision cases](docs/AI_USAGE.md)
- [Agent workflow rules](AGENTS.md) and [architecture decisions](plan/PLAN.md)
- Course requirements are published in Moodle and are not redistributed here.
