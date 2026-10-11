# PLAN: Architecture decisions

Architecture authority (see `AGENTS.md`). Requirements live in `docs/SPECIFICATION.md`; this file records how they are built.

Status markers:
- **[confirmed]**: decided or approved by the user (all seeds approved 2026-10-11).
- **[seed, review]**: proposed by main; awaiting user review.

## Decisions

**D1. Stack [confirmed].** The backend is Python 3.14 with FastAPI and uses uv for dependencies. The frontend is React with TypeScript.

**D2. Repository layout [confirmed].** Two sibling apps, `backend/` and `frontend/`, each with its own toolchain. The current root `pyproject.toml`, `uv.lock` and `.python-version` move into `backend/`. Root keeps only docs, plans and workflow files.

**D3. Backend layering [confirmed].** The dependency direction is `api` → `services` → `repositories`, with `domain` underneath. `domain` holds pure functions and dataclasses: split calculation, rounding, balances and settle-up. Business rules are tested there without HTTP or a database.

**D4. Money representation [confirmed].** Inside the backend, money is integer cents. The API accepts and returns decimal strings with at most 2 decimal places. Pydantic validates the format and the range 0.01–1,000,000.00, and rejects anything else with HTTP 422 (AC3, AC4). Resolves the spec's "Currency" uncertainty.

**D5. Rounding rule [confirmed, from spec AC2].** For an equal split, each share is `total // n`. The remaining `total % n` cents go one each to participants in order of group join time, earliest first.

**D6. Settle-up algorithm [confirmed, from spec AC6].** Greedy: repeatedly match the largest creditor with the largest debtor and transfer `min(credit, debt)`. Ties are broken by join order. This produces at most n−1 transfers.

**D7. Persistence [confirmed].** SQLite through SQLAlchemy 2.0 with typed `Mapped[...]` models. Alembic migrations run on startup. The test suite uses a fresh SQLite database per test. AC8 is tested by restarting the app against the same database file.

**D8. Authentication [confirmed].** Username and password registration. Passwords are hashed with Argon2 (`pwdlib`). Login issues a short-lived JWT bearer token through OAuth2's password flow. The frontend keeps the token in memory, with `sessionStorage` as a fallback.

**D9. Authorization [confirmed, from spec AC5].** Every group-scoped endpoint resolves membership in the service layer. A non-member gets HTTP 404 and an unauthenticated request gets HTTP 401.

**D10. Frontend [confirmed].** Built with Vite, React and TypeScript in strict mode. TanStack Query handles server state and React Router handles pages. There is no global state library. The API client is typed by hand to match the backend schemas.

**D11. Quality tooling [confirmed].**
- Backend: pytest, pytest-cov, httpx through FastAPI's TestClient, Ruff for lint and format, and mypy in strict mode.
- Frontend: Vitest with React Testing Library, ESLint, Prettier, and `tsc --noEmit`.
- Coverage gate: at least 90% line and branch coverage on `backend/app` [confirmed].

**D12. Course deliverables [confirmed, from course requirements].**
- `docs/TESTING.md`: maps each acceptance criterion to its checks.
- `docs/AI_USAGE.md`: the tools, three decision cases, and the comparison of implementing one feature twice.
- A faulty and a corrected version of one test, with both run logs.
- A `v1.0` git tag at the first-working-version milestone, so the change request can be traced.
