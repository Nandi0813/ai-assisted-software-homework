---
status: accepted
completion_date: 2026-10-11
implementation_notes: "Accepted: isort import order (ruff I001), one ruff format reflow, mypy-required test annotations; optional _compound_expenses helper used."
---

# 03: Domain: balances and settle-up

## 1. Goal, non-goals

**Goal.** Pure, fully tested rules that:
- compute each member's balance from expenses and payments (AC1);
- suggest settle-up transfers with the greedy algorithm (D6, AC6).

**Non-goals:**
- No persistence, HTTP or membership storage.
- No rule for leaving a group: AC7 is enforced by a service in stage 05, which reads these balances.
- No new dependencies.

## 2. Owned files

Created:
- `backend/app/domain/balances.py`
- `backend/tests/domain/test_balances.py`

Helpers to reuse:
- `format_cents` at `backend/app/domain/money.py:29`, used in an error message.
- `split_equal` at `backend/app/domain/splits.py:18` and `split_exact` at `backend/app/domain/splits.py:31`, used only in tests to build realistic expense shares.

There are no callers yet; stages 05 and 06 will call these functions. Allowed imports: the standard library (`dataclasses`, `collections.abc`) and `app.domain.*` only.

## 3. Signatures, types, behavior

Sign convention: a positive balance means the group owes the member money (a creditor). A negative balance means the member owes money (a debtor). Members are `int` IDs.

`members` is ordered by join time, earliest first, and must include every member who ever took part in an expense or payment, including members who have left (AC7 keeps their history). Every returned dict follows `members` order.

### Data types

All are `@dataclass(frozen=True, slots=True)`:
- `ExpenseEntry`: `payer_id: int`, `shares: Mapping[int, int]`. The shares are already split in cents, for example the output of `split_equal`. The expense total is `sum(shares.values())`.
- `PaymentEntry`: `from_id: int`, `to_id: int`, `amount_cents: int`. Money paid by `from_id` to `to_id`.
- `Transfer`: `from_id: int`, `to_id: int`, `amount_cents: int`. A suggested payment from a debtor to a creditor.

`class BalanceError(ValueError)`: no extra members.

### `compute_balances(members: Sequence[int], expenses: Iterable[ExpenseEntry], payments: Iterable[PaymentEntry]) -> dict[int, int]`

1. **Validate members.** Iterate in order. The first ID already seen raises `BalanceError(f"duplicate member: {m}")`. Then `balances = {m: 0 for m in members}`.
2. **Apply each expense, in order:**
   - If `payer_id` is not in `balances`, raise `BalanceError(f"unknown member: {payer_id}")`.
   - For each `(p, share)` in `shares.items()`, in order: if `p` is not in `balances`, raise `BalanceError(f"unknown member: {p}")`.
   - Only after all checks pass for this expense: `balances[payer_id] += sum(shares.values())`, then for each `(p, share)`: `balances[p] -= share`.
3. **Apply each payment, in order.** Checks, in this order:
   1. `from_id` not in `balances` raises `BalanceError(f"unknown member: {from_id}")`.
   2. `to_id` not in `balances` raises `BalanceError(f"unknown member: {to_id}")`.
   3. `from_id == to_id` raises `BalanceError("payment sender and recipient must differ")`.
   4. `amount_cents < 1` raises `BalanceError("payment amount must be positive")`.

   Then `balances[from_id] += amount_cents` and `balances[to_id] -= amount_cents`.
4. Return `balances`.

### `settle_up(balances: Mapping[int, int]) -> list[Transfer]`

Iteration order of `balances` is join order.

1. **Check the total.** Let `s = sum(balances.values())`. If `s != 0`, raise `BalanceError(f"balances must sum to zero, got {format_cents(s)}")`.
2. **Split by sign, in iteration order:**
   - `creditors = {p: b for p, b in balances.items() if b > 0}`
   - `debtors = {p: -b for p, b in balances.items() if b < 0}`
3. **Loop.** `transfers: list[Transfer] = []`. While `creditors` is not empty:
   1. `c = max(creditors, key=creditors.__getitem__)`. Python's `max` returns the first maximal key in iteration order, which gives the earliest-joiner tie-break.
   2. `d = max(debtors, key=debtors.__getitem__)`.
   3. `amount = min(creditors[c], debtors[d])`.
   4. Append `Transfer(from_id=d, to_id=c, amount_cents=amount)`.
   5. Subtract `amount` from both `creditors[c]` and `debtors[d]`, and delete any entry that reaches 0.
4. Return `transfers`.

The total is zero, so `debtors` empties at the same time as `creditors`. Each iteration removes at least one party and the last removes two, so `len(transfers) <= n - 1`, where n is the number of non-zero balances. When every balance is zero, the result is `[]`.

## 4. Edit recipe, in order

All paths are under `backend/`.

1. Create `app/domain/balances.py`. Imports:
   - `dataclass` from `dataclasses`;
   - `Iterable`, `Mapping` and `Sequence` from `collections.abc`;
   - `format_cents` from `app.domain.money`.

   Then define `ExpenseEntry`, `PaymentEntry`, `Transfer`, `BalanceError`, `compute_balances` and `settle_up` from section 3.
2. Create `tests/domain/test_balances.py` from section 6.
   - Use `pytest.raises(BalanceError, match=re.escape(<message>))` for every error assertion.
   - Use tuple argument names in `parametrize`.

## 5. Edge cases

| Call | Expected |
|------|----------|
| `compute_balances([1, 2, 3], [ExpenseEntry(1, {1: 3000, 2: 3000, 3: 3000})], [])` | `{1: 6000, 2: -3000, 3: -3000}` (AC1) |
| …the same, plus payment `PaymentEntry(2, 1, 3000)` | `{1: 3000, 2: 0, 3: -3000}` |
| `compute_balances([1, 2], [], [])` | `{1: 0, 2: 0}` |
| `settle_up({1: 6000, 2: -3000, 3: -3000})` | `[Transfer(2, 1, 3000), Transfer(3, 1, 3000)]` (the debtor tie goes to the earlier joiner, 2) |
| `settle_up({1: 1000, 2: 1000, 3: -2000})` | `[Transfer(3, 1, 1000), Transfer(3, 2, 1000)]` (the creditor tie goes to 1) |
| `settle_up({1: 5000, 2: -2000, 3: 3000, 4: -6000})` | `[Transfer(4, 1, 5000), Transfer(2, 3, 2000), Transfer(4, 3, 1000)]` (3 transfers = n−1) |
| `settle_up({1: 0, 2: 0})` | `[]` |
| `settle_up({})` | `[]` |
| `settle_up({1: 100, 2: -50})` | `BalanceError("balances must sum to zero, got 0.50")` |

Expected values for `Transfer(a, b, c)` mean `Transfer(from_id=a, to_id=b, amount_cents=c)`.

## 6. Tests

`tests/domain/test_balances.py`. Imports:
- `re`, `pytest`;
- from `app.domain.balances`: `BalanceError`, `ExpenseEntry`, `PaymentEntry`, `Transfer`, `compute_balances`, `settle_up`;
- from `app.domain.splits`: `split_equal`, `split_exact`.

Balances:
1. **`test_ac1_balances_after_equal_split`**: the first row of the section 5 table.
   - Expense: `ExpenseEntry(payer_id=1, shares=split_equal(9000, [1, 2, 3]))`.
   - Assert the result `== {1: 6000, 2: -3000, 3: -3000}`.
2. **`test_ac1_payment_reduces_balances`**: the same expense plus `PaymentEntry(from_id=2, to_id=1, amount_cents=3000)`.
   - Assert `== {1: 3000, 2: 0, 3: -3000}`.
3. **`test_balances_without_activity_are_zero`**: `compute_balances([1, 2], [], []) == {1: 0, 2: 0}`.
4. **`test_balances_payer_need_not_participate`**: `compute_balances([1, 2, 3], [ExpenseEntry(1, {2: 500, 3: 500})], [])`.
   - Assert `== {1: 1000, 2: -500, 3: -500}`.
5. **`test_balances_keep_join_order`**: `list(compute_balances([3, 1, 2], [], []))` `== [3, 1, 2]`.
6. **`test_balances_always_sum_to_zero`**: the compound fixture below. Assert `sum(result.values()) == 0` and `result == {1: 7500, 2: -2834, 3: -333, 4: -2833, 5: -1500}`.
7. **`test_compute_balances_rejects_invalid`**, parametrized on `("members", "expenses", "payments", "message")`:
   - `([1, 1], [], [], "duplicate member: 1")`
   - `([1, 2], [ExpenseEntry(9, {1: 100})], [], "unknown member: 9")`
   - `([1, 2], [ExpenseEntry(1, {9: 100})], [], "unknown member: 9")`
   - `([1, 2], [], [PaymentEntry(9, 1, 100)], "unknown member: 9")`
   - `([1, 2], [], [PaymentEntry(1, 9, 100)], "unknown member: 9")`
   - `([1, 2], [], [PaymentEntry(1, 1, 100)], "payment sender and recipient must differ")`
   - `([1, 2], [], [PaymentEntry(1, 2, 0)], "payment amount must be positive")`
   - `([1, 2], [], [PaymentEntry(1, 2, -5)], "payment amount must be positive")`

**Compound fixture.** A module-level helper `def _compound_balances() -> dict[int, int]` returns `compute_balances([1, 2, 3, 4, 5], expenses, [])` with these expenses:
- `ExpenseEntry(1, split_equal(10000, [1, 2, 3, 4, 5]))`
- `ExpenseEntry(3, split_equal(2501, [2, 3, 4]))`
- `ExpenseEntry(5, split_exact(999, {1: 500, 5: 499}))`

Settle-up:
8. **`test_ac6_settle_up_after_equal_split`**: `settle_up({1: 6000, 2: -3000, 3: -3000}) == [Transfer(2, 1, 3000), Transfer(3, 1, 3000)]`.
9. **`test_settle_up_creditor_tie_goes_to_earliest_joiner`**: the creditor-tie row of the section 5 table.
10. **`test_ac6_settle_up_mixed_balances`**: the 4-member row of the section 5 table. Also assert `len(result) == 3`.
11. **`test_ac6_settle_up_compound`**: `settle_up(_compound_balances())` `== [Transfer(2, 1, 2834), Transfer(4, 1, 2833), Transfer(5, 1, 1500), Transfer(3, 1, 333)]`.
12. **`test_settle_up_all_settled`**, parametrized on `"balances"` with cases `{}` and `{1: 0, 2: 0}`. Assert `settle_up(balances) == []`.
13. **`test_settle_up_rejects_non_zero_sum`**: the last row of the section 5 table.
14. **`test_ac6_recording_transfers_settles_everyone`**, parametrized on `"balances"` with these cases:
    - `{1: 6000, 2: -3000, 3: -3000}`
    - `{1: 1000, 2: 1000, 3: -2000}`
    - `{1: 5000, 2: -2000, 3: 3000, 4: -6000}`
    - `{1: -1, 2: -1, 3: -1, 4: 3}`
    - `{1: 250, 2: -100, 3: -100, 4: -50}`

    Steps:
    1. `transfers = settle_up(balances)`.
    2. `nonzero = sum(1 for b in balances.values() if b != 0)`.
    3. Assert `len(transfers) <= nonzero - 1`.
    4. Assert every `t.amount_cents > 0`.
    5. Build `after = dict(balances)`. For each `t`: `after[t.from_id] += t.amount_cents` and `after[t.to_id] -= t.amount_cents`.
    6. Assert `all(v == 0 for v in after.values())`.
15. **`test_ac6_settling_through_payments_zeroes_compound_balances`**:
    1. `balances = _compound_balances()`.
    2. `payments = [PaymentEntry(t.from_id, t.to_id, t.amount_cents) for t in settle_up(balances)]`.
    3. Recompute `compute_balances([1, 2, 3, 4, 5], <the same three expenses>, payments)`.
    4. Assert every value is `0`.

    To share the expense list, `_compound_balances` may be split into a module-level `_compound_expenses() -> list[ExpenseEntry]` plus `_compound_balances()` that calls it. This is the only structural freedom in this stage.

### Focused checks (Tier 1)

Run in `backend/` and report each exit code:
- `uv run pytest tests/domain/test_balances.py -q`
- `uv run ruff check app/domain/balances.py tests/domain/test_balances.py`
- `uv run ruff format --check app/domain/balances.py tests/domain/test_balances.py`
- `uv run mypy app/domain/balances.py tests/domain/test_balances.py`

## 7. Stop conditions

Stop and report; do not work around:
- Any section 6 assertion fails. Report the case, the actual value, and `path:line`. Do not change expected values or the algorithm.
- Ruff or mypy reports an error that a mechanical change cannot fix.
- Any step needs a file outside section 2, a new dependency, or a forbidden import.

Done when: both files exist, all four focused checks exit 0, and the report is delivered.

## Acceptance receipt (2026-10-11)

Main reviewed the diff against sections 2–6. The check order, messages, sign convention, greedy loop, fixtures and expected values match the spec.

The implementer's Tier 1 first pass failed on I001 (import order) and on formatting. It fixed both mechanically with `ruff check --fix` and `ruff format`, and the final pass exited 0 on all four checks. Main then ran the backend Tier 2 gate. Logs are in `.logs/03-gate-*.log`. Frontend inputs are unchanged, so the stage 01 receipt still stands.

| Step | Command | Exit | Summary |
|------|---------|------|---------|
| backend tests | `uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90` | 0 | 123 passed, 1 warning; coverage 100.00% (148 stmts, 68 branches) |
| backend types | `uv run mypy` | 0 | no issues in 13 source files |
| backend lint | `uv run ruff check .` | 0 | All checks passed |
| backend format | `uv run ruff format --check .` | 0 | 13 files already formatted |

**Accepted deviations:**
- The imports are sorted with `collections.abc` before `dataclasses`, as Ruff requires.
- One test line was reflowed by `ruff format`.
- Test functions carry the annotations that `mypy --strict` requires.
- The optional `_compound_expenses()` helper from section 6 was used.
