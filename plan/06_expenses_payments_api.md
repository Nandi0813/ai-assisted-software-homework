---
status: in_progress
completion_date: null
implementation_notes: ""
---

# 06: Expenses, payments, balances and settle-up API

> **Dual implementation (PLAN D13).** This spec is implemented twice from the same base commit:
> - the Claude Code `implementer`, on `main`;
> - Google Antigravity, on `compare/06-antigravity`.
>
> It must be self-contained. Implementers follow `AGENTS.md` and this file only.

## 1. Goal, non-goals

**Goal.** Group-scoped API for:
- expenses with equal, exact and percent splits: create, list, update and delete, where only the creator may update or delete;
- payments between members: record and list;
- balances, together with the suggested settle-up transfers.

It wires the accepted domain rules (stages 02–03) to persistence and HTTP, and covers AC1, AC2, AC3, AC4, AC6 and AC8 through the API, plus AC5 for the new endpoints.

**Non-goals:**
- Leaving a group (AC7) and rejoining. Those come in stage 06b, which builds on this stage's balances.
- Expense timestamps, categories, currencies and pagination.
- Frontend.

## 2. Owned files

All paths are under `backend/`.

| File | Action |
|------|--------|
| `app/repositories/models.py` | modify: add `ExpenseShare`, `Expense`, `Payment` |
| `app/migrations/versions/rev_0003_create_ledger.py` | create |
| `app/repositories/groups.py` | modify: add `member_rows` |
| `app/repositories/ledger.py` | create: `LedgerRepository` |
| `app/services/groups.py` | modify: extract the module function `require_active_member` |
| `app/services/ledger.py` | create: inputs, errors, views, `LedgerService` |
| `app/api/deps.py` | modify: add `get_ledger_service`, `LedgerServiceDep` |
| `app/api/ledger.py` | create: schemas, error mapping, `router` |
| `app/main.py` | modify: include `ledger_router` |
| `tests/test_ledger.py` | create |
| `tests/test_migrations.py` | modify: expected tables and head revision |

**Existing code to reuse** (verified at commit `35240c3`):

| Symbol | Location |
|--------|----------|
| `parse_amount`, `MoneyError` | `app/domain/money.py:14`, `:7` |
| `format_cents` | `app/domain/money.py:29` |
| `split_equal`, `split_exact`, `split_percent`, `SplitError` | `app/domain/splits.py:18`, `:31`, `:46`, `:9` |
| `ExpenseEntry`, `PaymentEntry`, `Transfer`, `compute_balances`, `settle_up` | `app/domain/balances.py:8`, `:14`, `:21`, `:31`, `:69` |
| `GroupRepository` | `app/repositories/groups.py:7` |
| `GroupNotFoundError` | `app/services/groups.py:10` |
| `GroupService._require_active_member` | `app/services/groups.py:34` (callers: `get_group` `:55`, `add_member` `:58`) |
| `SessionDep`, `CurrentUserDep` | `app/api/deps.py:42`, `:71` |
| router includes | `app/main.py:32-34` |

No new dependencies. `app/domain/*` is not modified.

## 3. Signatures, types, behavior

Every money value in the API is a **decimal string** (e.g. `"30.00"`), and every money value inside the backend is an `int` of cents (D4). Users are identified by `user_id`. **Join order** means `GroupMember.id` ascending (D5).

### 3.1 Models (`app/repositories/models.py`)

Define them in this order, after `GroupMember`. Each constraint name below is the short name; the naming convention prefixes it. Import `CheckConstraint` and `relationship`.

**`ExpenseShare(Base)`:**
- `__tablename__ = "expense_shares"`
- `__table_args__`:
  - `UniqueConstraint("expense_id", "user_id", name="uq_expense_shares_expense_user")`
  - `CheckConstraint("amount_cents >= 0", name="amount_non_negative")`
- `id: Mapped[int]` (primary key)
- `expense_id: Mapped[int]` → `ForeignKey("expenses.id")`
- `user_id: Mapped[int]` → `ForeignKey("users.id")`
- `amount_cents: Mapped[int]`
- `percent_bp: Mapped[int | None]`

**`Expense(Base)`:**
- `__tablename__ = "expenses"`
- `__table_args__`:
  - `CheckConstraint("amount_cents > 0", name="amount_positive")`
  - `CheckConstraint("split_type IN ('equal', 'exact', 'percent')", name="split_type_valid")`
- `id: Mapped[int]` (primary key)
- `group_id`: `ForeignKey("groups.id")`
- `payer_id`: `ForeignKey("users.id")`
- `created_by`: `ForeignKey("users.id")`
- `description: Mapped[str] = mapped_column(String(200))`
- `amount_cents: Mapped[int]`
- `split_type: Mapped[str] = mapped_column(String(10))`
- `shares: Mapped[list[ExpenseShare]] = relationship(cascade="all, delete-orphan", order_by="ExpenseShare.id", lazy="selectin")`

**`Payment(Base)`:**
- `__tablename__ = "payments"`
- `__table_args__`:
  - `CheckConstraint("amount_cents > 0", name="amount_positive")`
  - `CheckConstraint("from_id <> to_id", name="distinct_parties")`
- `id` (primary key)
- `group_id`: `ForeignKey("groups.id")`
- `from_id`, `to_id` and `created_by`: each `ForeignKey("users.id")`
- `amount_cents: Mapped[int]`

### 3.2 Migration `rev_0003_create_ledger.py`

- Docstring `"""create expenses, expense_shares and payments tables\n\nRevision ID: 0003\nRevises: 0002\n"""`.
- `revision = "0003"` and `down_revision = "0002"`, with typed module variables as in `rev_0002`.
- `upgrade()` creates three tables in this order: `expenses`, `expense_shares`, `payments`. Every column is `nullable=False` except `expense_shares.percent_bp`, which is `nullable=True`. Every constraint is named explicitly, matching the convention output.

`expenses`:

| Column | Type |
|--------|------|
| `id` | `sa.Integer(), primary_key=True` |
| `group_id` | `sa.Integer()` |
| `payer_id` | `sa.Integer()` |
| `created_by` | `sa.Integer()` |
| `description` | `sa.String(200)` |
| `amount_cents` | `sa.Integer()` |
| `split_type` | `sa.String(10)` |

Constraints on `expenses`:
- `ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_expenses_group_id_groups")`
- `ForeignKeyConstraint(["payer_id"], ["users.id"], name="fk_expenses_payer_id_users")`
- `ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_expenses_created_by_users")`
- `CheckConstraint("amount_cents > 0", name="ck_expenses_amount_positive")`
- `CheckConstraint("split_type IN ('equal', 'exact', 'percent')", name="ck_expenses_split_type_valid")`

`expense_shares`:

| Column | Type |
|--------|------|
| `id` | `sa.Integer(), primary_key=True` |
| `expense_id` | `sa.Integer()` |
| `user_id` | `sa.Integer()` |
| `amount_cents` | `sa.Integer()` |
| `percent_bp` | `sa.Integer(), nullable=True` |

Constraints on `expense_shares`:
- `ForeignKeyConstraint(["expense_id"], ["expenses.id"], name="fk_expense_shares_expense_id_expenses")`
- `ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_expense_shares_user_id_users")`
- `UniqueConstraint("expense_id", "user_id", name="uq_expense_shares_expense_user")`
- `CheckConstraint("amount_cents >= 0", name="ck_expense_shares_amount_non_negative")`

`payments`:

| Column | Type |
|--------|------|
| `id` | `sa.Integer(), primary_key=True` |
| `group_id` | `sa.Integer()` |
| `from_id` | `sa.Integer()` |
| `to_id` | `sa.Integer()` |
| `created_by` | `sa.Integer()` |
| `amount_cents` | `sa.Integer()` |

Constraints on `payments`:
- `ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_payments_group_id_groups")`
- `ForeignKeyConstraint(["from_id"], ["users.id"], name="fk_payments_from_id_users")`
- `ForeignKeyConstraint(["to_id"], ["users.id"], name="fk_payments_to_id_users")`
- `ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_payments_created_by_users")`
- `CheckConstraint("amount_cents > 0", name="ck_payments_amount_positive")`
- `CheckConstraint("from_id <> to_id", name="ck_payments_distinct_parties")`

`downgrade()` drops `payments`, then `expense_shares`, then `expenses`.

### 3.3 `GroupRepository.member_rows` (`app/repositories/groups.py`)

`member_rows(self, group_id: int) -> list[tuple[GroupMember, User]]` returns **every** member, active and inactive, in join order:
- `select(GroupMember, User).join(User, User.id == GroupMember.user_id)`
- `.where(GroupMember.group_id == group_id)`
- `.order_by(GroupMember.id)`
- then `list(self._session.execute(stmt).tuples())`.

### 3.4 `require_active_member` (`app/services/groups.py`)

- Add the module-level function `require_active_member(groups: GroupRepository, user: User, group_id: int) -> Group`. Its body is exactly the current body of `GroupService._require_active_member` (`:34-41`), using `groups` in place of `self._groups`.
- Delete the method `_require_active_member`, and replace its two call sites with `require_active_member(self._groups, user_or_actor, group_id)`, keeping the same argument at each site.

Behavior is unchanged.

### 3.5 `LedgerRepository` (`app/repositories/ledger.py`)

`ShareRow = tuple[int, int, int | None]`, a type alias meaning `(user_id, amount_cents, percent_bp)`.

`class LedgerRepository`, constructed with `__init__(self, session: Session) -> None`:
- `add_expense(self, *, group_id: int, payer_id: int, created_by: int, description: str, amount_cents: int, split_type: str, shares: list[ShareRow]) -> Expense`: build the `Expense` with `shares=[ExpenseShare(user_id=u, amount_cents=c, percent_bp=p) for u, c, p in shares]`, then `add`, `flush` and return it.
- `get_expense(self, group_id: int, expense_id: int) -> Expense | None`: `scalars(select(Expense).where(Expense.id == expense_id, Expense.group_id == group_id)).one_or_none()`.
- `list_expenses(self, group_id: int) -> list[Expense]`: filter by `group_id`, ordered by `Expense.id`.
- `replace_expense(self, expense: Expense, *, payer_id: int, description: str, amount_cents: int, split_type: str, shares: list[ShareRow]) -> Expense`:
  1. Set the four scalar fields.
  2. `expense.shares.clear()`, then **`self._session.flush()`**. The flush must come before the new shares are added; without it, the unique `(expense_id, user_id)` constraint conflicts.
  3. `expense.shares.extend(ExpenseShare(...) for each row)`, then `flush` and return.
- `delete_expense(self, expense: Expense) -> None`: `self._session.delete(expense)`, then `flush`. The cascade removes the shares.
- `add_payment(self, *, group_id: int, from_id: int, to_id: int, created_by: int, amount_cents: int) -> Payment`: add, `flush`, return.
- `list_payments(self, group_id: int) -> list[Payment]`: ordered by `Payment.id`.

### 3.6 `app/services/ledger.py`

**Inputs and views.** All are `@dataclass(frozen=True, slots=True)`.
- `ShareInput`: `user_id: int`, `value: str`. The value is an amount for exact splits and a percent for percent splits.
- `ExpenseInput`:
  - `description: str`
  - `amount: str`
  - `payer_id: int`
  - `split_type: Literal["equal", "exact", "percent"]`
  - `participants: list[int]` (used for `equal`)
  - `shares: list[ShareInput]` (used for `exact` and `percent`)
- `MemberBalance`: `user_id: int`, `username: str`, `balance_cents: int`, `active: bool`.
- `BalanceView`: `members: list[MemberBalance]`, `transfers: list[Transfer]`.

**Errors.** Each is `class X(Exception)`.
- `ExpenseNotFoundError`
- `NotExpenseCreatorError`
- `LedgerValidationError`: the message is the HTTP `detail`, accessed with `str(err)`.

`class LedgerService`, constructed with `__init__(self, session: Session) -> None`, which stores `self._session`, `self._groups = GroupRepository(session)`, `self._ledger = LedgerRepository(session)` and `self._users = UserRepository(session)`.

**`_active_order(self, group_id: int) -> dict[int, int]`.** Maps each active member's `user_id` to its join index, counting from 0:
- `active = [m for m, _ in self._groups.member_rows(group_id) if m.active]`
- return `{m.user_id: i for i, m in enumerate(active)}`

**`_resolve(self, group_id: int, data: ExpenseInput) -> tuple[int, list[ShareRow]]`.** The checks run in exactly this order. The first failure raises `LedgerValidationError(<message>)`.
1. `total = parse_amount(data.amount)`. On `MoneyError as e`, raise with the message `str(e)`.
2. `order = self._active_order(group_id)`.
3. If `data.payer_id not in order`, raise with `"payer is not a member of this group"`.
4. **`equal`:**
   1. For each `p` in `data.participants`, in the given order: if `p not in order`, raise with `f"participant {p} is not a member of this group"`.
   2. `ordered = sorted(data.participants, key=order.__getitem__)`.
   3. `split = split_equal(total, ordered)`. On `SplitError as e`, raise with `str(e)`.
   4. The rows are `[(u, c, None) for u, c in split.items()]`.
5. **`exact` or `percent`:**
   1. `seen: set[int] = set()`. For each `s` in `data.shares`, in the given order:
      - if `s.user_id in seen`, raise with `f"duplicate participant: {s.user_id}"`;
      - `seen.add(s.user_id)`;
      - if `s.user_id not in order`, raise with `f"participant {s.user_id} is not a member of this group"`.
   2. Build `values: dict[int, int] = {}`. For each `s` in `sorted(data.shares, key=lambda s: order[s.user_id])`, set `values[s.user_id] = parse_amount(s.value)`. On `MoneyError`, raise with `str(e)`.
   3. **`exact`:** `split = split_exact(total, values)`, and the rows are `[(u, c, None) ...]`.
   4. **`percent`:** `split = split_percent(total, values)`, and the rows are `[(u, split[u], values[u]) for u in split]`.
   5. On `SplitError`, raise with `str(e)`.
6. Return `(total, rows)`.

**Public methods.** Each one starts with `require_active_member(self._groups, user, group_id)`, which raises `GroupNotFoundError`. Each method that writes data ends with `self._session.commit()`.

- **`create_expense(self, user: User, group_id: int, data: ExpenseInput) -> Expense`:** `_resolve`, then `add_expense(created_by=user.id, ...)`, then commit, then return.
- **`list_expenses(self, user: User, group_id: int) -> list[Expense]`.**
- **`update_expense(self, user: User, group_id: int, expense_id: int, data: ExpenseInput) -> Expense`:**
  1. Check membership.
  2. `expense = get_expense(...)`. If it is `None`, raise `ExpenseNotFoundError`.
  3. If `expense.created_by != user.id`, raise `NotExpenseCreatorError`.
  4. `_resolve`, then `replace_expense`, then commit, then return.
- **`delete_expense(self, user: User, group_id: int, expense_id: int) -> None`:** the same steps 1–3, then `delete_expense`, then commit.
- **`record_payment(self, user: User, group_id: int, from_id: int, to_id: int, amount: str) -> Payment`.** The checks run in this order, and each failure raises `LedgerValidationError`:
  1. `parse_amount`, with the message `str(e)`.
  2. `order = _active_order`.
  3. `from_id not in order` gives `f"user {from_id} is not a member of this group"`.
  4. `to_id not in order` gives `f"user {to_id} is not a member of this group"`.
  5. `from_id == to_id` gives `"payment sender and recipient must differ"`.

  Then `add_payment(created_by=user.id, ...)`, commit and return.
- **`list_payments(self, user: User, group_id: int) -> list[Payment]`.**
- **`balances(self, user: User, group_id: int) -> BalanceView`:**
  1. `rows = self._groups.member_rows(group_id)`.
  2. `ids = [m.user_id for m, _ in rows]`.
  3. `expenses = [ExpenseEntry(e.payer_id, {s.user_id: s.amount_cents for s in e.shares}) for e in list_expenses]`.
  4. `payments = [PaymentEntry(p.from_id, p.to_id, p.amount_cents) for p in list_payments]`.
  5. `bal = compute_balances(ids, expenses, payments)`.
  6. `members = [MemberBalance(m.user_id, u.username, bal[m.user_id], m.active) for m, u in rows if m.active or bal[m.user_id] != 0]`.
  7. Return `BalanceView(members, settle_up(bal))`.

### 3.7 `app/api/deps.py`

Append `get_ledger_service(session: SessionDep) -> LedgerService` and `LedgerServiceDep = Annotated[LedgerService, Depends(get_ledger_service)]`.

### 3.8 `app/api/ledger.py`

**Request schemas** (Pydantic):
- `Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]`
- `EqualSplit`: `type: Literal["equal"]`, `participants: list[int]`
- `ExactShareIn`: `user_id: int`, `amount: str`
- `ExactSplit`: `type: Literal["exact"]`, `shares: list[ExactShareIn]`
- `PercentShareIn`: `user_id: int`, `percent: str`
- `PercentSplit`: `type: Literal["percent"]`, `shares: list[PercentShareIn]`
- `Split = Annotated[EqualSplit | ExactSplit | PercentSplit, Field(discriminator="type")]`
- `ExpenseRequest`: `description: Description`, `amount: str`, `payer_id: int`, `split: Split`
- `PaymentRequest`: `from_id: int`, `to_id: int`, `amount: str`

**Response schemas:**
- `ShareOut`: `user_id: int`, `amount: str`, `percent: str | None`
- `ExpenseResponse`: `id: int`, `description: str`, `amount: str`, `payer_id: int`, `created_by: int`, `split_type: str`, `shares: list[ShareOut]`
- `PaymentResponse`: `id: int`, `from_id: int`, `to_id: int`, `amount: str`, `created_by: int`
- `MemberBalanceOut`: `user_id: int`, `username: str`, `balance: str`, `active: bool`
- `TransferOut`: `from_id: int`, `from_username: str`, `to_id: int`, `to_username: str`, `amount: str`
- `BalancesResponse`: `members: list[MemberBalanceOut]`, `transfers: list[TransferOut]`

**Helpers:**
- `_to_input(body: ExpenseRequest) -> ExpenseInput`, by `isinstance` on `body.split`:
  - `EqualSplit` gives `participants=list(split.participants)` and `shares=[]`.
  - `ExactSplit` gives `participants=[]` and `shares=[ShareInput(s.user_id, s.amount) ...]`.
  - `PercentSplit` gives `participants=[]` and `shares=[ShareInput(s.user_id, s.percent) ...]`.
  - `split_type=body.split.type` in every case.
- `_expense_out(e: Expense) -> ExpenseResponse`: amounts through `format_cents`. In each share, `percent=format_cents(s.percent_bp) if s.percent_bp is not None else None`, and the shares follow `e.shares` order.
- `_payment_out(p: Payment) -> PaymentResponse`.
- `_balances_out(v: BalanceView) -> BalancesResponse`: `names = {m.user_id: m.username for m in v.members}`. Each transfer's usernames come from `names`.
- `@contextmanager def _ledger_errors() -> Iterator[None]` maps these exceptions, each raised `from None`:

  | Exception | Status | `detail` |
  |-----------|--------|----------|
  | `GroupNotFoundError` | 404 | `"group not found"` |
  | `ExpenseNotFoundError` | 404 | `"expense not found"` |
  | `NotExpenseCreatorError` | 403 | `"only the creator can modify this expense"` |
  | `LedgerValidationError as e` | 422 | `str(e)` |

**`router = APIRouter(prefix="/groups/{group_id}", tags=["ledger"])`.** Every endpoint takes `group_id: int, user: CurrentUserDep, service: LedgerServiceDep`, and calls the service inside `with _ledger_errors():`.

| Method and path | Status | Response | Service call |
|-----------------|--------|----------|--------------|
| `POST /expenses` (body `ExpenseRequest`) | 201 | `ExpenseResponse` | `create_expense(user, group_id, _to_input(body))` |
| `GET /expenses` | 200 | `list[ExpenseResponse]` | `list_expenses` |
| `PUT /expenses/{expense_id}` (body `ExpenseRequest`) | 200 | `ExpenseResponse` | `update_expense` |
| `DELETE /expenses/{expense_id}` | 204 | no body (`-> None`) | `delete_expense` |
| `POST /payments` (body `PaymentRequest`) | 201 | `PaymentResponse` | `record_payment(user, group_id, body.from_id, body.to_id, body.amount)` |
| `GET /payments` | 200 | `list[PaymentResponse]` | `list_payments` |
| `GET /balances` | 200 | `BalancesResponse` | `balances` |

### 3.9 `app/main.py`

Include `ledger_router` with `prefix="/api"` after `groups_router`.

## 4. Edit recipe, in order

All paths are under `backend/`.

1. `models.py`: add the three models (section 3.1).
2. Create `rev_0003_create_ledger.py` (section 3.2).
3. `repositories/groups.py`: add `member_rows` (section 3.3).
4. `services/groups.py`: extract `require_active_member` (section 3.4). Run `uv run pytest tests/test_groups.py -q`; it must pass unchanged before you continue.
5. Create `repositories/ledger.py`, then `services/ledger.py` (sections 3.5 and 3.6).
6. `api/deps.py` (section 3.7). Create `api/ledger.py` (section 3.8). Edit `main.py` (section 3.9).
7. Tests (section 6).

## 5. Edge cases

**Setup S**, unless stated otherwise:
- register alice (id 1), bob (id 2) and carol (id 3);
- alice creates group 1 and adds `"bob"`, then `"carol"`, so the join order is 1, 2, 3.

**Body E**: `{"description": "Dinner", "amount": "90.00", "payer_id": 1, "split": {"type": "equal", "participants": [1, 2, 3]}}`.

| Situation | Expected |
|-----------|----------|
| alice `POST` E | 201; shares `[{1,"30.00",null},{2,"30.00",null},{3,"30.00",null}]`; balances 1 `"60.00"`, 2 `"-30.00"`, 3 `"-30.00"` (AC1) |
| `"100.00"` equal with participants `[3, 2, 1]` | shares, in join order: 1 `"33.34"`, 2 `"33.33"`, 3 `"33.33"` (AC2) |
| join order 1, 3, 2 (carol added before bob); `"100.00"` equal `[1, 2, 3]` | shares listed 1 `"33.34"`, 3 `"33.33"`, 2 `"33.33"` |
| exact `"100.00"` with 1 `"50.00"`, 2 `"40.00"` | 422 `"exact shares sum to 90.00, expected 100.00"`; nothing saved (AC3) |
| percent `"10.00"` with 1 `"33.33"`, 2 `"33.33"`, 3 `"33.34"` | shares `"3.33"`/`"33.33"`, `"3.33"`/`"33.33"`, `"3.34"`/`"33.34"` |
| percent with 1 `"50"`, 2 `"40"` | 422 `"percentages sum to 90.00%, expected 100.00%"` |
| E after alice paid; bob pays alice `"30.00"` | balances 1 `"30.00"`, 2 `"0.00"`, 3 `"-30.00"` |
| E; carol pays `"30.00"` equal `[2, 3]` | balances 1 `"60.00"`, 2 `"-45.00"`, 3 `"-15.00"`; transfers bob→alice `"45.00"`, carol→alice `"15.00"` (AC6) |
| bob `PUT` or `DELETE` alice's expense | 403 `"only the creator can modify this expense"` |
| `/groups/1/expenses/999` | 404 `"expense not found"` |

## 6. Tests

### `tests/test_ledger.py`

Imports: `pytest`, `TestClient`, `Settings`, `create_app`.

Module helpers (type every parameter):
- `PASSWORD = "correct-horse"`.
- `def _headers(client: TestClient, username: str, register: bool = True) -> dict[str, str]`:
  - If `register` is true, `POST /api/auth/register` and assert 201.
  - Log in with form data and assert 200.
  - Return the bearer header.
- `def _setup(client: TestClient) -> tuple[dict[str, str], dict[str, str], dict[str, str]]`: performs **Setup S** (asserting 201 on the group creation and on each member add) and returns `(alice, bob, carol)`.
- `def _equal(amount: str, participants: list[int], payer_id: int = 1, description: str = "Dinner") -> dict[str, object]`: builds the equal body.
- `def _exact(amount: str, shares: list[tuple[int, str]], payer_id: int = 1) -> dict[str, object]`: builds the exact body, with `"description": "Dinner"`.
- `def _percent(amount: str, shares: list[tuple[int, str]], payer_id: int = 1) -> dict[str, object]`: builds the percent body, with `"description": "Dinner"`.
- `def _balances(client: TestClient, headers: dict[str, str]) -> list[tuple[int, str]]`: `GET /api/groups/1/balances`, assert 200, and return `[(m["user_id"], m["balance"]) for m in body["members"]]`.

`URL = "/api/groups/1"`.

#### Expenses and balances

1. **`test_ac1_equal_split_balances`**:
   - alice `POST {URL}/expenses` with `_equal("90.00", [1, 2, 3])` gives 201.
   - The body is exactly `{"id": 1, "description": "Dinner", "amount": "90.00", "payer_id": 1, "created_by": 1, "split_type": "equal", "shares": [{"user_id": 1, "amount": "30.00", "percent": None}, {"user_id": 2, "amount": "30.00", "percent": None}, {"user_id": 3, "amount": "30.00", "percent": None}]}`.
   - `_balances(...) == [(1, "60.00"), (2, "-30.00"), (3, "-30.00")]`.
2. **`test_ac2_extra_cent_to_earliest_joiner`**: `_equal("100.00", [3, 2, 1])`. `[(s["user_id"], s["amount"]) for s in body["shares"]] == [(1, "33.34"), (2, "33.33"), (3, "33.33")]`. **This list comparison asserts order**, closing the stage 02 follow-up.
3. **`test_ac2_rounding_follows_join_order_not_user_id`**:
   - Do not use `_setup`. Register alice, bob and carol; alice creates a group, adds `"carol"`, then `"bob"`.
   - `_equal("100.00", [1, 2, 3])` gives shares `[(1, "33.34"), (3, "33.33"), (2, "33.33")]`.
4. **`test_ac3_exact_split`**:
   - `_exact("90.00", [(3, "15.00"), (1, "50.00"), (2, "25.00")])` gives 201.
   - The shares are `[(1, "50.00"), (2, "25.00"), (3, "15.00")]`, in join order.
   - Balances are `[(1, "40.00"), (2, "-25.00"), (3, "-15.00")]`.
5. **`test_ac3_exact_split_sum_mismatch`**:
   - `_exact("100.00", [(1, "50.00"), (2, "40.00")])` gives 422 `{"detail": "exact shares sum to 90.00, expected 100.00"}`.
   - Then `GET {URL}/expenses` gives `[]`.
6. **`test_ac3_percent_split`**: `_percent("10.00", [(1, "33.33"), (2, "33.33"), (3, "33.34")])` gives 201, and `body["shares"] == [{"user_id": 1, "amount": "3.33", "percent": "33.33"}, {"user_id": 2, "amount": "3.33", "percent": "33.33"}, {"user_id": 3, "amount": "3.34", "percent": "33.34"}]`.
7. **`test_ac3_percent_split_must_total_100`**: `_percent("10.00", [(1, "50"), (2, "40")])` gives 422 `{"detail": "percentages sum to 90.00%, expected 100.00%"}`.
8. **`test_ac4_rejects_invalid_expense`**, parametrized on `("body", "detail")`:
   - `(_equal("0", [1, 2]), "amount must be at least 0.01")`
   - `(_equal("-5.00", [1, 2]), "invalid amount format: '-5.00'")`
   - `(_equal("1.234", [1, 2]), "invalid amount format: '1.234'")`
   - `(_equal("1000000.01", [1, 2]), "amount must not exceed 1000000.00")`
   - `(_equal("10.00", []), "at least one participant is required")`
   - `(_equal("10.00", [1, 2], payer_id=99), "payer is not a member of this group")`
   - `(_equal("10.00", [1, 99]), "participant 99 is not a member of this group")`
   - `(_equal("10.00", [1, 2, 1]), "duplicate participant: 1")`
   - `(_exact("10.00", [(1, "5.00"), (1, "5.00")]), "duplicate participant: 1")`
   - `(_exact("10.00", [(1, "abc"), (2, "5.00")]), "invalid amount format: 'abc'")`
   - `(_percent("10.00", [(1, "100"), (99, "0")]), "participant 99 is not a member of this group")`

   Assert 422 and `{"detail": detail}`, then `GET {URL}/expenses == []`. The parameter `body` is typed `dict[str, object]`.
9. **`test_ac4_rejects_malformed_request`**, parametrized on `"body"` (`dict[str, object]`):
   - `{**_equal("10.00", [1]), "description": ""}`
   - `{**_equal("10.00", [1]), "description": "x" * 201}`
   - `{**_equal("10.00", [1]), "amount": 10}`
   - `{**_equal("10.00", [1]), "split": {"type": "weird", "participants": [1]}}`
   - `{"description": "x", "amount": "1.00", "payer_id": 1}`

   Assert 422 for each.
10. **`test_list_expenses_in_creation_order`**: post `_equal("10.00", [1, 2])` and `_equal("20.00", [2, 3])`. `GET` gives ids `[1, 2]` and amounts `["10.00", "20.00"]`.
11. **`test_update_expense_by_creator`**:
    - Post E. alice `PUT {URL}/expenses/1` with `_equal("60.00", [1, 2])` gives 200, with shares `[(1, "30.00"), (2, "30.00")]` and `amount == "60.00"`.
    - Balances are `[(1, "30.00"), (2, "-30.00"), (3, "0.00")]`.
12. **`test_update_can_change_split_type`**:
    - Post E, then `PUT` with `_percent("90.00", [(1, "50"), (2, "50")])` gives 200.
    - `split_type == "percent"`, and the shares are `[(1, "45.00"), (2, "45.00")]`. This exercises the clear-flush-extend path in `replace_expense`.
13. **`test_only_creator_can_modify_expense`**, parametrized on `"method"` with cases `"PUT"` and `"DELETE"`:
    - alice posts E.
    - bob `client.request(method, f"{URL}/expenses/1", json=_equal("10.00", [1]) if method == "PUT" else None, headers=bob)` gives 403 `{"detail": "only the creator can modify this expense"}`.
14. **`test_delete_expense_by_creator`**: post E. `DELETE` gives 204. `GET` expenses gives `[]`. Balances are `[(1, "0.00"), (2, "0.00"), (3, "0.00")]`.
15. **`test_expense_not_found`**, parametrized on `("method", "path")`:
    - Cases: `("PUT", "/api/groups/1/expenses/999")`, `("DELETE", "/api/groups/1/expenses/999")`, `("PUT", "/api/groups/2/expenses/1")`, `("DELETE", "/api/groups/2/expenses/1")`.
    - Setup: `_setup`, alice posts E to group 1, and alice creates group 2 with `{"name": "Other"}`.
    - Use `json=_equal("10.00", [1])` for `PUT` and `None` for `DELETE`.
    - Assert 404 `{"detail": "expense not found"}`.

#### Payments and settle-up

16. **`test_ac1_payment_reduces_balances`**:
    - Post E. bob `POST {URL}/payments` with `{"from_id": 2, "to_id": 1, "amount": "30.00"}` gives 201 `{"id": 1, "from_id": 2, "to_id": 1, "amount": "30.00", "created_by": 2}`.
    - Balances are `[(1, "30.00"), (2, "0.00"), (3, "-30.00")]`.
17. **`test_payment_rejects_invalid`**, parametrized on `("from_id", "to_id", "amount", "detail")`:
    - `(2, 1, "0.00", "amount must be at least 0.01")`
    - `(2, 1, "ten", "invalid amount format: 'ten'")`
    - `(99, 1, "10.00", "user 99 is not a member of this group")`
    - `(2, 99, "10.00", "user 99 is not a member of this group")`
    - `(2, 2, "10.00", "payment sender and recipient must differ")`

    Assert 422 and the detail; then `GET {URL}/payments == []`.
18. **`test_list_payments`**: two payments (2→1 `"5.00"`, 3→1 `"7.50"`). `GET` gives amounts `["5.00", "7.50"]` in id order.
19. **`test_ac6_settle_up_suggestions`**:
    - Post E, then carol posts `_equal("30.00", [2, 3], payer_id=3)`.
    - `GET /balances` gives `members == [{"user_id": 1, "username": "alice", "balance": "60.00", "active": True}, {"user_id": 2, "username": "bob", "balance": "-45.00", "active": True}, {"user_id": 3, "username": "carol", "balance": "-15.00", "active": True}]`.
    - It also gives `transfers == [{"from_id": 2, "from_username": "bob", "to_id": 1, "to_username": "alice", "amount": "45.00"}, {"from_id": 3, "from_username": "carol", "to_id": 1, "to_username": "alice", "amount": "15.00"}]`.
20. **`test_ac6_recording_suggested_transfers_settles_everyone`**:
    1. Same setup as test 19.
    2. For each transfer in the response, alice posts `{"from_id": t["from_id"], "to_id": t["to_id"], "amount": t["amount"]}` and gets 201.
    3. Then `_balances == [(1, "0.00"), (2, "0.00"), (3, "0.00")]` and `transfers == []`.

#### Access control and persistence

21. **`test_ac5_non_member_gets_404`**, parametrized on `("method", "path", "json_body")`, with `json_body` typed `dict[str, object] | None`.
    - Setup: register alice and bob (no `_setup`). alice creates group 1 and posts `_equal("10.00", [1])`. bob is not added.
    - Cases:
      - `("GET", "/api/groups/1/expenses", None)`
      - `("POST", "/api/groups/1/expenses", _equal("10.00", [1]))`
      - `("PUT", "/api/groups/1/expenses/1", _equal("10.00", [1]))`
      - `("DELETE", "/api/groups/1/expenses/1", None)`
      - `("GET", "/api/groups/1/payments", None)`
      - `("POST", "/api/groups/1/payments", {"from_id": 1, "to_id": 1, "amount": "1.00"})`
      - `("GET", "/api/groups/1/balances", None)`
    - bob gets 404 `{"detail": "group not found"}`.
22. **`test_ac5_ledger_requires_authentication`**: the same 7 `(method, path, json_body)` cases, with no setup and no headers. Each gives 401 `{"detail": "not authenticated"}`.
23. **`test_ac8_ledger_survives_restart`** (`settings` fixture):
    1. `with TestClient(create_app(settings)) as first`: `_setup`, post E, and bob pays alice `"30.00"`.
    2. `with TestClient(create_app(settings)) as second`: `alice = _headers(second, "alice", register=False)`.
    3. Assert `_balances(second, alice) == [(1, "30.00"), (2, "0.00"), (3, "-30.00")]` and that `GET` expenses has length 1.

### `tests/test_migrations.py`

Modify:
- `test_migrations_create_tables`: add `"expenses"`, `"expense_shares"` and `"payments"` to the expected set.
- `test_migrations_are_idempotent`: expect `["0003"]`.

Add test 24, **`test_migration_0003_preserves_groups`**:
1. `command.upgrade(make_alembic_config(c), "0002")`, inside `engine.begin()`.
2. Insert a user `('legacy', 'h')`, a group `('Trip')`, and a membership row with `group_id 1`, `user_id 1` and `active 1`, using plain SQL `INSERT`s.
3. `run_migrations(engine)`.
4. Assert `SELECT id, name FROM groups` gives `[(1, "Trip")]`, and `SELECT group_id, user_id, active FROM group_members` gives `[(1, 1, 1)]`.

### Focused checks (Tier 1)

Run in `backend/`:
- `uv run pytest tests -q` (whole suite, no coverage)
- `uv run ruff check app tests`
- `uv run ruff format --check app tests`
- `uv run mypy`

Every check must exit 0, and the pytest output must contain no warnings.

## 7. Stop conditions

Stop and report; do not work around:
- `test_migrations_match_models` reports a diff. Paste it verbatim.
- `tests/test_groups.py` fails after step 4.
- Any section 6 assertion fails. Report the test, the actual status and body, and `path:line`. Do not change expected values.
- mypy or ruff errors that a mechanical change cannot fix. No `Any`, no `type: ignore`, no `noqa`, no excluded files.
- A file outside section 2, a new dependency, or a change in `app/domain/` would be needed.

Done when: all four checks exit 0 with no warnings, and the report lists the files changed, the commands with their exit codes, the test totals, the deviations, the hazards, and **the wall-clock start and end time** (D13 measurement).
