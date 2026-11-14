---
status: accepted
completion_date: 2026-11-14
implementation_notes: "409 detail f-string split in two literals for E501 (same text). Implementer hook blocked its ruff format and mypy runs; main ran them in the gate."
---

# 06b: Leave a group and rejoin (AC7)

## 1. Goal, non-goals

**Goal.**
- `POST /api/groups/{group_id}/leave`: an active member with balance exactly 0 leaves (HTTP 204). A non-zero balance gives HTTP 409 with the outstanding amount in `detail` (AC7).
- Past expenses and payments stay unchanged after leaving (AC7: history stays).
- Re-adding a former member reactivates the existing `group_members` row, so the member keeps the original join position (PLAN D5 tie-break).
- `GET /api/groups/{id}` (and the other group detail responses) gain `former_members`, so the UI can name former members in history.
- Payments may name a former member as sender or recipient. Reason: deleting an old expense can give a former member a non-zero balance; settle-up then suggests a transfer with them, and AC6 requires that it can be recorded.
- Remove the unused `LedgerService._users` (stage 06 review finding).

**Non-goals.**
- No migration: `group_members.active` exists since `rev_0002`.
- No change to expense validation: a new or edited expense still accepts only active members as payer/participants.
- No frontend.

## 2. Owned files

All paths under `backend/`.

| File | Action |
|------|--------|
| `app/repositories/groups.py` | modify: delete `active_member_users` (`:34`) |
| `app/services/groups.py` | modify: `GroupView.former_members`, `_view`, `add_member` reactivation |
| `app/api/groups.py` | modify: `GroupDetailResponse.former_members`, `_detail` |
| `app/services/ledger.py` | modify: `OutstandingBalanceError`, `leave_group`, `record_payment` member check, drop `_users` |
| `app/api/ledger.py` | modify: 409 mapping, `leave_group` route |
| `tests/test_groups.py` | modify: `:33` expectation, new rejoin test |
| `tests/test_ledger.py` | modify: new AC7 tests, parametrize lists |

**Callers / reuse** (verified with `grep -n` at `64f615a`):

| Symbol | Location |
|--------|----------|
| `GroupRepository.member_rows` | `app/repositories/groups.py:44` (returns `(GroupMember, User)` in join order, active and inactive) |
| `GroupRepository.get_membership` | `app/repositories/groups.py:20` |
| `GroupRepository.active_member_users` | `app/repositories/groups.py:34`; only caller `app/services/groups.py:45` |
| `require_active_member` | `app/services/groups.py:28` |
| `GroupService._view` | `app/services/groups.py:44`; callers `:51`, `:57`, `:68` |
| `GroupService.add_member` | `app/services/groups.py:59` |
| `LedgerService.balances` | `app/services/ledger.py:197` |
| `LedgerService.record_payment` | `app/services/ledger.py:168` |
| `LedgerService._users` | `app/services/ledger.py:63` (no reader) |
| `_ledger_errors` | `app/api/ledger.py:194` |
| `format_cents` | `app/domain/money.py:29` (already imported in `app/api/ledger.py`) |
| ledger `router` (prefix `/groups/{group_id}`) | `app/api/ledger.py:209` |

Allowed imports: nothing new beyond the symbols above. No new dependencies.

## 3. Signatures, types, behavior

### 3.1 `app/services/groups.py`

```
@dataclass(frozen=True, slots=True)
class GroupView:
    group: Group
    members: list[User]          # active, join order
    former_members: list[User]   # inactive, join order
```

`GroupService.add_member(actor, group_id, username) -> GroupView`, check order:
1. `require_active_member(...)` (unchanged).
2. Unknown user: `UserNotFoundError` (unchanged).
3. `membership = get_membership(group_id, target.id)`.
   - `membership is not None and membership.active`: `AlreadyMemberError` (unchanged message mapping, 409).
   - `membership is not None` (inactive): set `membership.active = True`. No new row.
   - `None`: `self._groups.add_member(...)` (unchanged).
4. `commit`, return `_view(group)`.

### 3.2 `app/api/groups.py`

`GroupDetailResponse` gains `former_members: list[MemberResponse]`, declared after `members`. `_detail` fills it from `view.former_members` the same way as `members`.

### 3.3 `app/services/ledger.py`

```
class OutstandingBalanceError(Exception):
    def __init__(self, balance_cents: int) -> None: ...   # stores self.balance_cents; super().__init__(balance_cents)

LedgerService.leave_group(self, user: User, group_id: int) -> None
```

`leave_group`, in order:
1. `view = self.balances(user, group_id)` (this already runs `require_active_member`, so a non-member gets `GroupNotFoundError`).
2. `balance = next(m.balance_cents for m in view.members if m.user_id == user.id)`. An active member is always in `view.members`.
3. `balance != 0`: `raise OutstandingBalanceError(balance)`. Nothing changes.
4. `membership = self._groups.get_membership(group_id, user.id)`; `assert membership is not None` with the inline comment `# guaranteed by require_active_member`; set `membership.active = False`; `self._session.commit()`.

`record_payment`: after parsing the amount, replace the `order = self._active_order(group_id)` lookup with the set of **all** member user ids of the group: `{m.user_id for m, _ in self._groups.member_rows(group_id)}`. The two membership checks and their messages are unchanged; `from_id == to_id` check unchanged.

Delete `self._users = UserRepository(session)` from `__init__` and the then-unused `UserRepository` import.

### 3.4 `app/api/ledger.py`

In `_ledger_errors`, add a branch (after `LedgerValidationError`):
`OutstandingBalanceError as e` → `HTTPException(status_code=409, detail=f"cannot leave the group with an outstanding balance of {format_cents(e.balance_cents)}")`.

New route on the ledger `router`:
`@router.post("/leave", status_code=204)` `def leave_group(group_id: int, user: CurrentUserDep, service: LedgerServiceDep) -> None`, body: `with _ledger_errors(): service.leave_group(user, group_id)`.

| Situation | Status | Body |
|-----------|--------|------|
| no token | 401 | `{"detail": "not authenticated"}` |
| non-member / former member / missing group | 404 | `{"detail": "group not found"}` |
| balance ≠ 0 | 409 | `{"detail": "cannot leave the group with an outstanding balance of -30.00"}` (amount via `format_cents`) |
| balance = 0 | 204 | empty |

### 3.5 `app/repositories/groups.py`

Delete `active_member_users`. `_view` uses `member_rows`:
`rows = self._groups.member_rows(group.id)`; `members = [u for m, u in rows if m.active]`; `former_members = [u for m, u in rows if not m.active]`.

## 4. Edit recipe, in order

1. `app/repositories/groups.py`: delete `active_member_users`.
2. `app/services/groups.py`: add the `former_members` field; rewrite `_view` per 3.5; rewrite step 3 of `add_member` per 3.1.
3. `app/api/groups.py`: add the field and fill it in `_detail`.
4. `app/services/ledger.py`: add `OutstandingBalanceError` after `LedgerValidationError`; remove `_users` and its import; change `record_payment` per 3.3; add `leave_group` after `balances`.
5. `app/api/ledger.py`: import `OutstandingBalanceError`; add the 409 branch; add the route after `get_balances`.
6. Tests per section 6.

## 5. Edge cases

Setup `S` = `_setup` in `tests/test_ledger.py`: alice id 1 (creator), bob id 2, carol id 3, group 1, join order alice, bob, carol.

| Input | Expected |
|-------|----------|
| S; alice pays 90.00 equal [1,2,3]; bob leaves | 409, `"... outstanding balance of -30.00"`; bob still sees group (200) |
| same; alice leaves | 409, `"... of 60.00"` |
| S; alice pays 90.00 equal [1,2,3]; payment 2→1 30.00; bob leaves | 204; bob `GET /api/groups/1` 404; bob `GET /api/groups` `[]`; alice sees `members` alice, carol and `former_members` bob; expense 1 unchanged incl. bob's share 30.00; balances `[(1,"30.00"),(3,"-30.00")]` |
| S; carol leaves with no expenses | 204 |
| bob leaves twice | second call 404 `"group not found"` |
| S; bob leaves; alice re-adds bob | 201; `members` ids `[1,2,3]` in that order; `former_members` `[]` |
| after rejoin, alice posts 10.01 equal [3,2] payer 1 | shares `[(2,"5.01"),(3,"5.00")]`: bob keeps position before carol |
| S; 90.00 equal [1,2,3] by alice; 2→1 30.00; bob leaves; alice deletes expense 1 | balances members `[(1,"-30.00"),(2,"30.00"),(3,"0.00")]`, bob `active: false`; transfer 1→2 30.00; recording it gives 201; then balances `[(1,"0.00"),(3,"0.00")]` |
| payment with user 99 | unchanged: 422 `"user 99 is not a member of this group"` |

## 6. Tests

All test helpers are the existing typed ones (`_setup`, `_headers`, `_equal`, `_balances`, `_user`). New tests return `None` and annotate `client: TestClient`.

### `tests/test_groups.py`

- `test_create_group_makes_creator_member` (`:26`): add `"former_members": []` to the expected dict after `"members"`.
- New `test_ac7_rejoin_reactivates_membership`: alice, bob, carol registered via `_user`; alice creates "Trip", adds bob then carol (201 each). bob `POST /api/groups/1/leave` → 204. alice `GET /api/groups/1` → `former_members == [{"id": 2, "username": "bob"}]`. alice re-adds bob → 201 and `json()["members"] == [{"id":1,"username":"alice"},{"id":2,"username":"bob"},{"id":3,"username":"carol"}]`, `json()["former_members"] == []`. bob `GET /api/groups` → `[{"id": 1, "name": "Trip"}]`.

### `tests/test_ledger.py`, new section `#### Leaving and rejoining (AC7)` before `#### Access control and persistence`

- `test_ac7_member_with_balance_cannot_leave`: S; alice posts `_equal("90.00", [1, 2, 3])` (201). bob leave → 409, json `{"detail": "cannot leave the group with an outstanding balance of -30.00"}`. alice leave → 409, json `{"detail": "cannot leave the group with an outstanding balance of 60.00"}`. bob `GET /api/groups/1` → 200. `_balances(alice)` unchanged `[(1,"60.00"),(2,"-30.00"),(3,"-30.00")]`.
- `test_ac7_settled_member_can_leave_and_history_stays`: S; alice posts `_equal("90.00", [1, 2, 3])`; bob posts payment `{"from_id":2,"to_id":1,"amount":"30.00"}` (201). bob leave → 204, `content == b""`. bob `GET /api/groups/1` → 404; bob `GET /api/groups` → `[]`. alice `GET /api/groups/1` → `members` `[alice(1), carol(3)]`, `former_members` `[bob(2)]`. alice `GET {URL}/expenses` → one expense whose `shares` equal `[{"user_id":1,"amount":"30.00","percent":None},{"user_id":2,"amount":"30.00","percent":None},{"user_id":3,"amount":"30.00","percent":None}]`. alice `GET {URL}/payments` length 1. `_balances(alice) == [(1,"30.00"),(3,"-30.00")]`.
- `test_ac7_member_without_expenses_can_leave`: S; carol leave → 204; carol leave again → 404 `{"detail": "group not found"}`.
- `test_ac7_rejoined_member_keeps_join_position`: S; bob leave → 204; alice re-adds bob (`POST {URL}/members` `{"username":"bob"}`) → 201; alice posts `_equal("10.01", [3, 2])` (payer 1) → 201 and `json()["shares"] == [{"user_id":2,"amount":"5.01","percent":None},{"user_id":3,"amount":"5.00","percent":None}]`.
- `test_ac6_payment_with_former_member_settles`: S; alice posts `_equal("90.00", [1, 2, 3])`; bob pays 2→1 30.00; bob leave → 204; alice `DELETE {URL}/expenses/1` → 204. alice `GET {URL}/balances` → `members == [{"user_id":1,"username":"alice","balance":"-30.00","active":True},{"user_id":2,"username":"bob","balance":"30.00","active":False},{"user_id":3,"username":"carol","balance":"0.00","active":True}]`, `transfers == [{"from_id":1,"from_username":"alice","to_id":2,"to_username":"bob","amount":"30.00"}]`. alice posts payment 1→2 30.00 → 201. `_balances(alice) == [(1,"0.00"),(3,"0.00")]`.
- Both parametrize lists of `test_ac5_non_member_gets_404` and `test_ac5_ledger_requires_authentication`: append `("POST", "/api/groups/1/leave", None)`.

### Tier 1 commands (in `backend/`)

```
uv run pytest tests/test_groups.py tests/test_ledger.py -q
uv run ruff check app/repositories/groups.py app/services/groups.py app/api/groups.py app/services/ledger.py app/api/ledger.py tests/test_groups.py tests/test_ledger.py
uv run ruff format --check app/repositories/groups.py app/services/groups.py app/api/groups.py app/services/ledger.py app/api/ledger.py tests/test_groups.py tests/test_ledger.py
uv run mypy app/repositories/groups.py app/services/groups.py app/api/groups.py app/services/ledger.py app/api/ledger.py tests/test_groups.py tests/test_ledger.py
```

## 7. Stop conditions

Stop and report instead of improvising if:
- any existing test other than `test_create_group_makes_creator_member` needs a changed expectation;
- an expected value in section 5 or 6 does not match the real response;
- mypy needs `Any`, `cast` or `# type: ignore`;
- a migration seems necessary;
- a file outside section 2 needs editing.

## Acceptance receipt (2026-11-14)

Tier 2 gate, `backend/`, logs in `.logs/06b-*.log`:

| Command | Exit | Result |
|---------|------|--------|
| `uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90` | 0 | 241 passed; coverage 100.00% (815 stmts, 128 branches) |
| `uv run mypy` | 0 | no issues in 36 source files |
| `uv run ruff check .` | 0 | no issues |
| `uv run ruff format --check .` | 0 | 36 files already formatted |

Review: diff matches sections 3–4. Accepted deviation: split f-string (E501).
