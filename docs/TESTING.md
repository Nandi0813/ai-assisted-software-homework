# Testing

Every acceptance criterion (AC) from [`SPECIFICATION.md`](SPECIFICATION.md) maps to automated checks and, where the UI matters, to reproducible manual steps. Automated tests for criterion N are named `test_acN_<behavior>` (backend) or `acN …` (frontend).

## How to run

```bash
make test        # backend pytest + frontend vitest
make check       # lint, format check, typecheck, tests

# backend only (in backend/): full gate with coverage
uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90
# frontend only (in frontend/)
npm run test -- --run
```

Latest results (stage receipts in `plan/`): backend **241 passed, 100% line + branch coverage** (`plan/06b_leave_rejoin.md`); frontend **44+ tests passed**, lint, typecheck and build clean (`plan/08_frontend_expenses.md`, `plan/08c_fix_equal_split_new_members.md`).

Test layers:
- `backend/tests/domain/`: pure business rules (splits, rounding, balances, settle-up, money parsing), no HTTP or database.
- `backend/tests/test_*.py`: the HTTP API through FastAPI's `TestClient` against a fresh SQLite file per test.
- `frontend/src/**/*.test.tsx`: UI behaviour with React Testing Library and a mocked `fetch`.

## Criterion → checks

| AC | Rule | Automated checks | Manual check |
|----|------|------------------|--------------|
| 1 | Equal split: Alice pays 90.00 for 3 → +60.00 / −30.00 / −30.00 | `backend/tests/domain/test_splits.py::test_ac1_split_equal_divides_evenly`, `domain/test_balances.py::test_ac1_balances_after_equal_split`, `test_ledger.py::test_ac1_equal_split_balances`, `::test_ac1_payment_reduces_balances`; frontend `Expenses.test.tsx` "ac1 equal split sends all members", "ac1 equal split includes members added after the page loaded", `BalancesPanel.test.tsx` "ac1 shows balances with signs" | M1 |
| 2 | Rounding: 100.00 / 3 → 33.34, 33.33, 33.33; extra cents by join order | `domain/test_splits.py::test_ac2_split_equal_extra_cent_to_earliest_joiner`, `::test_ac2_split_equal_two_cent_remainder`, `::test_ac2_split_equal_remainder_follows_given_order`, `::test_split_equal_shares_always_sum_to_total` (28 combinations); `test_ledger.py::test_ac2_extra_cent_to_earliest_joiner`, `::test_ac2_rounding_follows_join_order_not_user_id`; `::test_ac7_rejoined_member_keeps_join_position` | M1 |
| 3 | Exact must sum to total, percent to 100%, else 422 and nothing saved | `domain/test_splits.py::test_ac3_split_exact_*`, `::test_ac3_split_percent_*`; `test_ledger.py::test_ac3_exact_split`, `::test_ac3_exact_split_sum_mismatch`, `::test_ac3_percent_split`, `::test_ac3_percent_split_must_total_100`; frontend "ac3 exact split sends entered shares", "ac3 percent split …", "ac3 shows the server rejection" | M2 |
| 4 | Invalid input → 422, no change: 0, negative, >2 decimals, >1,000,000.00, empty participants, non-member payer/participant | `domain/test_money.py::test_ac4_parse_amount_*`; `test_ledger.py::test_ac4_rejects_invalid_expense` (parametrized over every listed case, also asserts the expense list stays empty), `::test_ac4_rejects_malformed_request`, `::test_payment_rejects_invalid`; frontend "ac4 shows pydantic messages" | M2 |
| 5 | 401 unauthenticated; 404 for non-members, indistinguishable from a missing group | `test_auth.py::test_ac5_me_*`; `test_groups.py::test_ac5_non_member_gets_404`, `::test_ac5_missing_group_is_indistinguishable`, `::test_ac5_groups_require_authentication`; `test_ledger.py::test_ac5_non_member_gets_404`, `::test_ac5_ledger_requires_authentication` (every group endpoint, including `/leave`) | M3 |
| 6 | Settle-up: ≤ n−1 transfers; recording them all zeroes every balance | `domain/test_balances.py::test_ac6_recording_transfers_settles_everyone` (5 balance sets), `::test_ac6_settle_up_*`, `::test_ac6_settling_through_payments_zeroes_compound_balances`; `test_ledger.py::test_ac6_settle_up_suggestions`, `::test_ac6_recording_suggested_transfers_settles_everyone`, `::test_ac6_payment_with_former_member_settles`; frontend `SettleUpPanel.test.tsx` (3 `ac6` tests) | M1 |
| 7 | Non-zero balance can't leave (409 + amount in UI); zero balance can; history stays | `test_ledger.py::test_ac7_member_with_balance_cannot_leave`, `::test_ac7_settled_member_can_leave_and_history_stays`, `::test_ac7_member_without_expenses_can_leave`, `::test_ac7_rejoined_member_keeps_join_position`; `test_groups.py::test_ac7_rejoin_reactivates_membership`; frontend `GroupPage.test.tsx` "ac7 shows the outstanding amount when leaving is refused" | M4 |
| 8 | Data and balances survive a backend restart | `test_auth.py::test_ac8_users_survive_restart`, `test_groups.py::test_ac8_groups_survive_restart`, `test_ledger.py::test_ac8_ledger_survives_restart` (two app instances on the same database file); `test_migrations.py` (migrations from empty and idempotent) | M5 |

## Required demonstration cases

| Kind | Case | Check |
|------|------|-------|
| Normal case | AC1 equal split 90.00 / 3 | `test_ledger.py::test_ac1_equal_split_balances` |
| Edge case 1 | AC2 indivisible amount, leftover cent goes by **join order, not user id** | `test_ledger.py::test_ac2_rounding_follows_join_order_not_user_id` |
| Edge case 2 | AC6/AC7 a former member gets a non-zero balance after an old expense is deleted; the suggested transfer can still be recorded | `test_ledger.py::test_ac6_payment_with_former_member_settles` |
| Invalid input | AC4 amount `1.234`, `0`, `-5`, `1000000.01`, empty participants, non-member | `test_ledger.py::test_ac4_rejects_invalid_expense` |
| Unauthorised operation | AC5 non-member reads or changes a group → 404 | `test_ledger.py::test_ac5_non_member_gets_404` |
| Regression 1 | Alembic CLI must run outside pytest's path (defect found in stage 05b) | `backend/tests/test_migrations.py::test_alembic_cli_upgrade_runs_outside_pytest_path` |
| Regression 2 | Equal split must include members added after the group page loaded (defect found in the browser run, stage 08c) | `frontend/src/components/Expenses.test.tsx` "ac1 equal split includes members added after the page loaded" |

## Failing on the faulty version, passing on the fixed one

Both defects occurred for real during development; neither was planted.

1. **Alembic CLI cannot import `app` (stage 05b).** Expected: `alembic upgrade head` works from any directory. Faulty: `ModuleNotFoundError: No module named 'app'`, because only pytest's `pythonpath` made `app` importable. Fixed with `prepend_sys_path` in `alembic.ini`.
   - Faulty run: [`evidence/05b-alembic-cli-regression-before.log`](evidence/05b-alembic-cli-regression-before.log), exit 1.
   - Fixed run: [`evidence/05b-alembic-cli-regression-after.log`](evidence/05b-alembic-cli-regression-after.log), exit 0.
2. **Equal split forgets newly added members (stage 08c).** Expected (AC1): after alice adds bob on the group page, an equal 90.00 split goes to `[alice, bob]`. Faulty: `participants: [1]`, because the form stored the *included* members once at mount. Fixed by storing the *excluded* members.
   - Faulty run: [`evidence/08c-equal-split-regression-before.log`](evidence/08c-equal-split-regression-before.log), exit 1.
   - Fixed run: [`evidence/08c-equal-split-regression-after.log`](evidence/08c-equal-split-regression-after.log), exit 0.

## Manual checks (reproducible)

Start with `make reset-db && make dev`, open <http://localhost:5173>, register `alice`, `bob`, `carol` (password `password123`), log in as alice.

- **M1 (AC1, AC2, AC6).** Create group "Trip", add `bob` and `carol`. Add expense "Dinner" 90.00, equal. Expected balances: alice `60.00`, bob `-30.00`, carol `-30.00`. Add "Groceries" 100.00, equal. Expected row shares `alice 33.34, bob 33.33, carol 33.33`. Settle up shows `bob pays alice 63.33` and `carol pays alice 63.33` (2 ≤ n−1 transfers). Click each `Record`. Expected: all balances `0.00` and `Everyone is settled up.`
- **M2 (AC3, AC4).** Split `Exact amounts`, amount 50.00, alice 10.00, bob 10.00 → alert `exact shares sum to 20.00, expected 50.00`; no new row. Equal, amount `1.234` → alert `invalid amount format: '1.234'`; no new row.
- **M3 (AC5).** Log in as a fourth user `dave` in another browser; open `/groups/1` → `Group not found.` Log out and call `curl -i localhost:8000/api/groups` → `401`.
- **M4 (AC7).** With an unsettled balance click `Leave group` → alert `cannot leave the group with an outstanding balance of …`, still on the page. After settling, `Leave group` returns to `Your groups`; another member still sees the old expenses and the leaver under `Former members`.
- **M5 (AC8).** Stop `make dev` (Ctrl-C) and start it again; log in → the group, expenses, payments and balances are unchanged.

Browser run of M1, M2 and M4 on 2026-11-14 (Playwright, main agent): screenshot [`evidence/e2e-group-page.png`](evidence/e2e-group-page.png). This run found defect 2 above.
