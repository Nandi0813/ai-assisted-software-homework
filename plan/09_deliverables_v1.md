---
status: accepted
completion_date: 2026-11-14
implementation_notes: "Docs-only stage, written by main (AGENTS.md allows main to edit docs). No application code."
---

# 09: Deliverables for the first working version

## Goal

Everything the "first working version" milestone asks for, on top of the code from stages 01–08c:
- `README.md`: status, setup, UI first steps, links to testing and AI docs.
- `docs/TESTING.md`: each AC mapped to automated and manual checks; the required normal / edge / invalid / unauthorised / regression cases; two faulty-vs-fixed test runs (05b, 08c) with logs.
- `docs/AI_USAGE.md`: tools, phases, 8 decision-case candidates, the D14 working-method comparison. The D13 dual-tool section waits on the Gemini CLI run (see `plan/WHATS_NEXT.md`).
- Tag `v1.0` on the commit that closes this stage.

## Acceptance receipt (2026-11-14)

| Command | Exit | Result |
|---------|------|--------|
| `make check` | 0 | backend 241 passed, coverage 100.00%, mypy clean (36 files), ruff clean; frontend 9 files / 46 tests passed, lint, typecheck and build clean (`.logs/09-make-check.log`) |

Browser run of the manual checks M1, M2, M4, M5 (AC1, AC2, AC3, AC4, AC6, AC7, AC8): see the 08c receipt.
