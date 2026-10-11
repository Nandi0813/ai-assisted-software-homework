---
status: accepted
completion_date: 2026-10-11
implementation_notes: "Accepted: Arabic-Indic test input written as the escape \\u0661 (RUF001; noqa forbidden); mypy-required test annotations; ruff format reflow. Spec gap: tests compare dicts by value, so the input-order return contract is unasserted; stage 06 asserts the order at the API level."
---

# 02: Domain: money parsing and expense splitting

## 1. Goal, non-goals

**Goal.** Pure, fully tested business rules for:
- parsing and formatting money (D4);
- equal splits with join-order rounding (D5);
- exact splits;
- percentage splits.

These rules back AC1–AC4 (`docs/SPECIFICATION.md`).

**Non-goals:**
- No balances or settle-up (stage 03).
- No HTTP, Pydantic or database code.
- No membership checks: checking that participants belong to the group is a service-layer rule in stage 06.
- No new dependencies.

## 2. Owned files

Created:
- `backend/app/domain/__init__.py`: empty.
- `backend/app/domain/money.py`
- `backend/app/domain/splits.py`
- `backend/tests/domain/test_money.py`
- `backend/tests/domain/test_splits.py`

No `__init__.py` in `backend/tests/domain/`; the test file basenames are unique.

There are no callers yet; stage 06 will call these functions. Helpers to reuse: `format_cents` from `app/domain/money.py`, which this stage creates, is used by `splits.py` for error messages. No other repo helpers exist.

Allowed imports in `app/domain/*`: the standard library only (`re`, `typing`, `collections.abc`) and `app.domain.*`. Importing FastAPI, Pydantic or SQLAlchemy is forbidden (AGENTS.md invariant).

## 3. Signatures, types, behavior

Money is `int` cents throughout. Percentages are `int` basis points, where 1 bp = 0.01% and 100.00% = 10,000. Participant identifiers are `int` member IDs. Every `Sequence` or `Mapping` argument is ordered by group join time, earliest first. The caller guarantees that order; the domain treats iteration order as join order.

### `app/domain/money.py`

- `MAX_AMOUNT_CENTS: Final[int] = 100_000_000` (1,000,000.00).
- `class MoneyError(ValueError)`: no extra members.
- `_AMOUNT_RE` is a compiled regex for the pattern `([0-9]+)(?:\.([0-9]{1,2}))?`. Match it with `fullmatch`.
  - Use `[0-9]`, not `\d`. Python's `\d` also matches non-ASCII digits.
- `def parse_amount(text: str) -> int`. Converts a decimal amount string to cents. In order:
  1. `m = _AMOUNT_RE.fullmatch(text)`. If `m is None`, raise `MoneyError(f"invalid amount format: {text!r}")`.
  2. If `len(group(1)) > 1` and `group(1)` starts with `"0"`, raise the same format error. This rejects leading zeros such as `"01.00"`.
  3. `cents = int(group(1)) * 100 + int((group(2) or "").ljust(2, "0"))`.
  4. If `cents < 1`, raise `MoneyError("amount must be at least 0.01")`.
  5. If `cents > MAX_AMOUNT_CENTS`, raise `MoneyError("amount must not exceed 1000000.00")`.
  6. Return `cents`.
- `def format_cents(cents: int) -> str`. Signed, always 2 decimals, no thousands separator.
  - `sign = "-" if cents < 0 else ""`, `whole, frac = divmod(abs(cents), 100)`.
  - Return `f"{sign}{whole}.{frac:02d}"`.

### `app/domain/splits.py`

- `PERCENT_SCALE: Final[int] = 10_000`.
- `class SplitError(ValueError)`: no extra members.
- `def _require_positive_total(total_cents: int) -> None`: raises `SplitError("total must be positive")` if `total_cents < 1`.

#### `split_equal(total_cents: int, participants: Sequence[int]) -> dict[int, int]`

Checks, in this order:
1. `_require_positive_total`.
2. An empty `participants` raises `SplitError("at least one participant is required")`.
3. Iterate in order. The first ID already seen raises `SplitError(f"duplicate participant: {p}")`.

Then `base, remainder = divmod(total_cents, len(participants))`. Return a dict in input order, where the participant at index `i` gets `base + (1 if i < remainder else 0)`. Zero shares are allowed when `total_cents < len(participants)`.

#### `split_exact(total_cents: int, shares: Mapping[int, int]) -> dict[int, int]`

Checks, in this order:
1. `_require_positive_total`.
2. An empty mapping raises `SplitError("at least one participant is required")`.
3. Iterate in order. The first share `< 1` raises `SplitError(f"share must be positive for participant {p}")`.
4. Let `s = sum(shares.values())`. If `s != total_cents`, raise `SplitError(f"exact shares sum to {format_cents(s)}, expected {format_cents(total_cents)}")`.

Return `dict(shares)`, a new dict in input order.

#### `split_percent(total_cents: int, percents: Mapping[int, int]) -> dict[int, int]`

`percents` is in basis points. Checks, in this order:
1. `_require_positive_total`.
2. An empty mapping raises `SplitError("at least one participant is required")`.
3. Iterate in order. The first value `< 1` raises `SplitError(f"percentage must be positive for participant {p}")`.
4. Let `s = sum(percents.values())`. If `s != PERCENT_SCALE`, raise `SplitError(f"percentages sum to {format_cents(s)}%, expected 100.00%")`.

Allocation uses the largest-remainder method with a join-order tie-break:
- For each participant `p`, in order, `base[p], rem[p] = divmod(total_cents * percents[p], PERCENT_SCALE)`.
- `leftover = total_cents - sum(base.values())`. This is always `0 <= leftover < len(percents)`.
- Rank participants by `rem` descending, breaking ties by input position ascending. Use a stable sort of the ordered keys with the key `-rem[p]`.
- The first `leftover` participants in that ranking get `+1`.

Return the result dict in input order, not ranking order.

## 4. Edit recipe, in order

All paths are under `backend/`.

1. Create `app/domain/__init__.py`, empty.
2. Create `app/domain/money.py`:
   - imports: `re`, and `Final` from `typing`;
   - then `MAX_AMOUNT_CENTS`, `MoneyError`, `_AMOUNT_RE`, `parse_amount` and `format_cents` from section 3.
3. Create `app/domain/splits.py`:
   - imports: `Mapping` and `Sequence` from `collections.abc`, `Final` from `typing`, and `format_cents` from `app.domain.money`;
   - then `PERCENT_SCALE`, `SplitError`, `_require_positive_total`, `split_equal`, `split_exact` and `split_percent` from section 3.
4. Create `tests/domain/test_money.py` and `tests/domain/test_splits.py` from section 6.
   - Use `pytest.raises(<Error>, match=re.escape(<message>))` for every error assertion.
   - Use `@pytest.mark.parametrize` with tuple argument names, for example `("text", "expected")`, and lists of tuples.

## 5. Edge cases

| Call | Expected |
|------|----------|
| `parse_amount("1")` | `100` |
| `parse_amount("1.5")` | `150` |
| `parse_amount("0.01")` | `1` |
| `parse_amount("1000000")` | `100_000_000` |
| `parse_amount("1000000.01")` | `MoneyError("amount must not exceed 1000000.00")` |
| `parse_amount("0.00")` | `MoneyError("amount must be at least 0.01")` |
| `parse_amount("01.00")` | `MoneyError("invalid amount format: '01.00'")` |
| `parse_amount("١.00")` (Arabic-Indic digit) | `MoneyError("invalid amount format: '١.00'")` |
| `format_cents(-5)` | `"-0.05"` |
| `split_equal(10000, [1, 2, 3])` | `{1: 3334, 2: 3333, 3: 3333}` (AC2) |
| `split_equal(10000, [3, 1, 2])` | `{3: 3334, 1: 3333, 2: 3333}` |
| `split_equal(2, [1, 2, 3])` | `{1: 1, 2: 1, 3: 0}` |
| `split_exact(10000, {1: 5000, 2: 4000})` | `SplitError("exact shares sum to 90.00, expected 100.00")` (AC3) |
| `split_percent(1000, {1: 3333, 2: 3333, 3: 3334})` | `{1: 333, 2: 333, 3: 334}` |
| `split_percent(1, {1: 5000, 2: 5000})` | `{1: 1, 2: 0}` (a tie, so the earlier participant wins) |
| `split_percent(10000, {1: 5000, 2: 4000})` | `SplitError("percentages sum to 90.00%, expected 100.00%")` (AC3) |

## 6. Tests

### `tests/domain/test_money.py`

Imports: `re`, `pytest`, and from `app.domain.money`: `MAX_AMOUNT_CENTS`, `MoneyError`, `format_cents`, `parse_amount`.

1. **`test_ac4_parse_amount_valid`**, parametrized on `("text", "expected")`:
   - Cases: `("0.01", 1)`, `("1", 100)`, `("1.5", 150)`, `("33.34", 3334)`, `("1000000", 100_000_000)`, `("1000000.00", 100_000_000)`.
   - Assert `parse_amount(text) == expected`.
2. **`test_ac4_parse_amount_rejects_bad_format`**, parametrized on `"text"`:
   - Cases: `""`, `" 1.00"`, `"1.00 "`, `"-1.00"`, `"+1.00"`, `"1.234"`, `"1."`, `".5"`, `"01.00"`, `"1e3"`, `"1,00"`, `"abc"`, `"NaN"`, `"١.00"`.
   - Assert it raises `MoneyError` with the message `f"invalid amount format: {text!r}"`.
3. **`test_ac4_parse_amount_rejects_zero`**, parametrized on `"text"`:
   - Cases: `"0"`, `"0.0"`, `"0.00"`.
   - Message: `"amount must be at least 0.01"`.
4. **`test_ac4_parse_amount_rejects_over_max`**, parametrized on `"text"`:
   - Cases: `"1000000.01"`, `"99999999999"`.
   - Message: `"amount must not exceed 1000000.00"`.
5. **`test_format_cents`**, parametrized on `("cents", "expected")`:
   - Cases: `(0, "0.00")`, `(5, "0.05")`, `(150, "1.50")`, `(3334, "33.34")`, `(-3000, "-30.00")`, `(-5, "-0.05")`, `(MAX_AMOUNT_CENTS, "1000000.00")`.
6. **`test_parse_format_round_trip`**, parametrized on `"cents"`:
   - Cases: `1`, `99`, `100`, `3334`, `MAX_AMOUNT_CENTS`.
   - Assert `parse_amount(format_cents(cents)) == cents`.

### `tests/domain/test_splits.py`

Imports: `re`, `pytest`, and from `app.domain.splits`: `SplitError`, `split_equal`, `split_exact`, `split_percent`.

Equal splits:
1. **`test_ac1_split_equal_divides_evenly`**: `split_equal(9000, [1, 2, 3]) == {1: 3000, 2: 3000, 3: 3000}`.
2. **`test_ac2_split_equal_extra_cent_to_earliest_joiner`**:
   - `result = split_equal(10000, [1, 2, 3])`.
   - Assert `result == {1: 3334, 2: 3333, 3: 3333}` and `sum(result.values()) == 10000`.
3. **`test_ac2_split_equal_remainder_follows_given_order`**: `split_equal(10000, [3, 1, 2]) == {3: 3334, 1: 3333, 2: 3333}`.
4. **`test_ac2_split_equal_two_cent_remainder`**: `split_equal(1002, [1, 2, 3, 4]) == {1: 251, 2: 251, 3: 250, 4: 250}`.
5. **`test_split_equal_total_smaller_than_participants`**: `split_equal(2, [1, 2, 3]) == {1: 1, 2: 1, 3: 0}`.
6. **`test_split_equal_single_participant`**: `split_equal(1234, [7]) == {7: 1234}`.
7. **`test_split_equal_shares_always_sum_to_total`**, parametrized on `"total"` × `"count"`:
   - Use two stacked `parametrize` decorators: `total` in `[1, 2, 3, 99, 100, 10001, 100_000_000]` and `count` in `[1, 2, 3, 7]`.
   - Call `result = split_equal(total, list(range(1, count + 1)))`.
   - Assert `sum(result.values()) == total` and `max(result.values()) - min(result.values()) <= 1`.
8. **`test_split_equal_rejects_invalid`**, parametrized on `("total", "participants", "message")`:
   - `(0, [1], "total must be positive")`
   - `(-100, [1], "total must be positive")`
   - `(100, [], "at least one participant is required")`
   - `(100, [1, 2, 1], "duplicate participant: 1")`

Exact splits:
9. **`test_ac3_split_exact_accepts_matching_sum`**: `split_exact(10000, {1: 5000, 2: 3000, 3: 2000}) == {1: 5000, 2: 3000, 3: 2000}`.
10. **`test_ac3_split_exact_rejects_mismatched_sum`**, parametrized on `("shares", "message")`:
    - `({1: 5000, 2: 4000}, "exact shares sum to 90.00, expected 100.00")`
    - `({1: 6000, 2: 5000}, "exact shares sum to 110.00, expected 100.00")`
    - The total is `10000` in both cases.
11. **`test_split_exact_rejects_invalid`**, parametrized on `("total", "shares", "message")`:
    - `(0, {1: 0}, "total must be positive")`
    - `(100, {}, "at least one participant is required")`
    - `(10000, {1: 10000, 2: 0}, "share must be positive for participant 2")`
    - `(10000, {1: 10100, 2: -100}, "share must be positive for participant 2")`

Percentage splits:
12. **`test_ac3_split_percent_even`**: `split_percent(10000, {1: 5000, 2: 5000}) == {1: 5000, 2: 5000}`.
13. **`test_ac3_split_percent_largest_remainder`**: `split_percent(1000, {1: 3333, 2: 3333, 3: 3334}) == {1: 333, 2: 333, 3: 334}`.
14. **`test_split_percent_tie_goes_to_earliest_joiner`**:
    - Assert `split_percent(1, {1: 5000, 2: 5000}) == {1: 1, 2: 0}`.
    - Assert `split_percent(1, {2: 5000, 1: 5000}) == {2: 1, 1: 0}`.
15. **`test_split_percent_shares_always_sum_to_total`**, parametrized on `"total"`:
    - Cases: `[1, 7, 999, 10000, 100_000_000]`.
    - Assert `sum(split_percent(total, {1: 3333, 2: 3333, 3: 3334}).values()) == total`.
16. **`test_ac3_split_percent_rejects_bad_sum`**: `split_percent(10000, {1: 5000, 2: 4000})` raises with the message `"percentages sum to 90.00%, expected 100.00%"`.
17. **`test_split_percent_rejects_invalid`**, parametrized on `("total", "percents", "message")`:
    - `(0, {1: 10000}, "total must be positive")`
    - `(100, {}, "at least one participant is required")`
    - `(100, {1: 10000, 2: 0}, "percentage must be positive for participant 2")`

### Focused checks (Tier 1)

Run in `backend/` and report each exit code:
- `uv run pytest tests/domain -q`
- `uv run ruff check app/domain tests/domain`
- `uv run ruff format --check app/domain tests/domain`
- `uv run mypy app/domain tests/domain`

## 7. Stop conditions

Stop and report; do not work around:
- Any section 6 assertion fails after transcription. Report the failing case, the actual value, and `path:line`. Do not change expected values or the algorithm.
- Ruff or mypy reports an error that a purely mechanical change cannot fix (syntax, imports, formatting, an annotation already implied by section 3).
- Any step would need a file outside section 2, a new dependency, or an import that section 2 forbids.

Done when: every file in section 2 exists, all four focused checks exit 0, and the report is delivered.

## Acceptance receipt (2026-10-11)

Main reviewed the diff against sections 2–6. The algorithms, check order, messages and test cases match the spec.

The implementer's Tier 1 checks all exited 0 on the final pass. The first pass needed a `ruff format` reflow, which is a mechanical change, and the RUF001 fix below. Main then ran the backend Tier 2 gate. Logs are in `.logs/02-gate-*.log`. Frontend inputs are unchanged, so the stage 01 receipt still stands.

| Step | Command | Exit | Summary |
|------|---------|------|---------|
| backend tests | `uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90` | 0 | 96 passed, 1 warning; coverage 100.00% (89 stmts, 36 branches) |
| backend types | `uv run mypy` | 0 | no issues in 11 source files |
| backend lint | `uv run ruff check .` | 0 | All checks passed |
| backend format | `uv run ruff format --check .` | 0 | 11 files already formatted |

**Accepted deviations:**
- The Arabic-Indic digit input is written as the escape `"١.00"`. The literal character triggers RUF001, and `noqa` is forbidden. The value is identical.
- Test functions carry parameter and `-> None` annotations, which `mypy --strict` requires.

**Spec gap found by main:** dict `==` ignores key order, so no test asserts that results come back in input order. The values do prove which participant received the extra cent, so AC2 is covered. Stage 06 must assert the response order.
