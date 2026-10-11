SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND_HOST ?= 127.0.0.1
BACKEND_PORT ?= 8000
FRONTEND_PORT ?= 5173
DEV_DB := backend/splitledger.db
# Development-only secret, so tokens survive uvicorn auto-reloads. Never use outside local dev.
DEV_JWT_SECRET ?= dev-only-insecure-secret-0123456789abcdef

.PHONY: help install install-backend install-frontend dev dev-backend dev-frontend test test-backend test-frontend lint typecheck format check migrate reset-db build clean distclean

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*## ' Makefile | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: install-backend install-frontend ## Install backend and frontend dependencies

install-backend: ## Sync backend virtualenv (uv)
	cd backend && uv sync

install-frontend: ## Install frontend packages from the lockfile (npm ci)
	cd frontend && npm ci

frontend/node_modules/.package-lock.json: frontend/package-lock.json
	cd frontend && npm ci

dev: frontend/node_modules/.package-lock.json ## Run backend (:8000) and frontend (:5173) with reload; Ctrl-C stops both
	trap 'kill 0' INT TERM; \
	( $(MAKE) --no-print-directory dev-backend ) & \
	( $(MAKE) --no-print-directory dev-frontend ) & \
	wait

dev-backend: ## Run only the backend with reload
	cd backend && SPLITLEDGER_JWT_SECRET='$(DEV_JWT_SECRET)' uv run uvicorn app.main:app --reload --reload-dir app --host $(BACKEND_HOST) --port $(BACKEND_PORT)

dev-frontend: frontend/node_modules/.package-lock.json ## Run only the frontend dev server
	cd frontend && npm run dev -- --host 127.0.0.1 --port $(FRONTEND_PORT) --strictPort

test: test-backend test-frontend ## Run all tests

test-backend: ## Run backend tests
	cd backend && uv run pytest -q

test-frontend: frontend/node_modules/.package-lock.json ## Run frontend tests
	cd frontend && npm run test -- --run

lint: frontend/node_modules/.package-lock.json ## Lint and format-check both sides (no changes)
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd frontend && npm run lint
	cd frontend && npm run format:check

typecheck: frontend/node_modules/.package-lock.json ## Type-check both sides
	cd backend && uv run mypy
	cd frontend && npm run typecheck

format: frontend/node_modules/.package-lock.json ## Auto-format both sides (writes files)
	cd backend && uv run ruff check --fix .
	cd backend && uv run ruff format .
	cd frontend && npm run format

check: frontend/node_modules/.package-lock.json ## Full quality gate (coverage >= 90%, types, lint, tests, build)
	cd backend && uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90
	cd backend && uv run mypy
	cd backend && uv run ruff check .
	cd backend && uv run ruff format --check .
	cd frontend && npm run typecheck
	cd frontend && npm run lint
	cd frontend && npm run test -- --run
	cd frontend && npm run build

migrate: ## Apply database migrations to the dev database
	cd backend && uv run alembic upgrade head

reset-db: ## Delete the dev database and re-create it empty (DESTROYS dev data)
	rm -f "$(DEV_DB)"
	$(MAKE) migrate

build: frontend/node_modules/.package-lock.json ## Build the frontend for production
	cd frontend && npm run build

clean: ## Remove caches, coverage and build output (keeps deps and dev DB)
	rm -rf backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache backend/.coverage backend/htmlcov frontend/dist frontend/coverage .logs

distclean: clean ## Also remove installed dependencies (.venv, node_modules)
	rm -rf backend/.venv frontend/node_modules
