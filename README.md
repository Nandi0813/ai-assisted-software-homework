# SplitLedger

Group expense splitting web app. Members record shared expenses, see who owes whom, and settle up with a minimal set of transfers.

Individual homework project for the *AI Assisted Software Development* MSc course (2026).

> **Status:** in development. The backend domain rules, persistence and auth are done; the groups and expenses API and the UI are next. See [plan/00_index.md](plan/00_index.md).

## Tech stack

| Layer    | Technology                     |
|----------|--------------------------------|
| Backend  | Python 3.14, FastAPI, SQLite   |
| Frontend | React                          |
| Tooling  | [uv](https://docs.astral.sh/uv/) for Python dependencies |

## Documentation

- [Specification & acceptance criteria](docs/SPECIFICATION.md)
- [AI usage and decision cases](docs/AI_USAGE.md)
- [Agent workflow rules](AGENTS.md) and [architecture decisions](plan/PLAN.md)
- Course requirements are published in Moodle (not redistributed here).
