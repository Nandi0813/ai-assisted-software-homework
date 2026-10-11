---
status: accepted
completion_date: 2026-10-11
implementation_notes: "Addendum 05-A applied (dict[str, Any] replaced by dict[str, str] in tests). Accepted: ruff format reflows; bob registered only in the bob case of test 9."
---

# 05: Groups and members API

## 1. Goal, non-goals

**Goal:**
- Groups with members kept in join order:
  - create a group (the creator joins automatically);
  - list my groups;
  - show a group with its members;
  - add a registered user by username.
- Every group-scoped endpoint returns 404 for a non-member or a group that doesn't exist (AC5, D9), and 401 when unauthenticated.
- Migration `0002` must preserve existing users, and tests prove it. This is the first data-preservation evidence for the change request.

**Non-goals:**
- **Leaving a group (AC7) moves to stage 06**, because the non-zero-balance rule needs expenses and payments. The `active` column is created now, so stage 06 needs no schema change for it.
- No renaming or deleting groups, no invitations (spec: "no invitations"), no group admin role.
- No frontend changes.

## 2. Owned files

All paths are under `backend/`.

| File | Action |
|------|--------|
| `app/repositories/models.py` | modify: naming convention on `Base`; add `Group` and `GroupMember` |
| `app/repositories/groups.py` | create: `GroupRepository` |
| `app/services/groups.py` | create: errors, `GroupView`, `GroupService` |
| `app/api/groups.py` | create: schemas and `router` |
| `app/api/deps.py` | modify: add `get_group_service` and `GroupServiceDep` |
| `app/main.py` | modify: include `groups_router` |
| `app/db.py` | modify: remove the redundant `import alembic.config` (stage 04 finding) |
| `app/migrations/versions/rev_0002_create_groups.py` | create |
| `tests/test_groups.py` | create |
| `tests/test_migrations.py` | modify (see section 6) |

**Existing code to reuse:**
- `Base` at `app/repositories/models.py:5`.
- `User` at `app/repositories/models.py:9`.
- `UserRepository.get_by_username` in `app/repositories/users.py` (class at `:7`).
- `SessionDep` at `app/api/deps.py:41`.
- `CurrentUserDep` at `app/api/deps.py:63`.
- `include_router` calls at `app/main.py:31-32`.
- `make_alembic_config` at `app/db.py:27`.

Allowed new imports: SQLAlchemy, FastAPI, Pydantic, the standard library and `app.*`. No new dependencies.

## 3. Signatures, types, behavior

### `app/repositories/models.py`

1. Give `Base` a class attribute `metadata = MetaData(naming_convention={...})`, with exactly these keys:
   - `"ix": "ix_%(column_0_label)s"`
   - `"uq": "uq_%(table_name)s_%(column_0_name)s"`
   - `"ck": "ck_%(table_name)s_%(constraint_name)s"`
   - `"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"`

   There is no `"pk"` key. The existing explicit name `uq_users_username` is unchanged.
2. Add `class Group(Base)`:
   - `__tablename__ = "groups"`
   - `id: Mapped[int] = mapped_column(primary_key=True)`
   - `name: Mapped[str] = mapped_column(String(64))`
3. Add `class GroupMember(Base)`:
   - `__tablename__ = "group_members"`
   - `__table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user"),)`
   - `id: Mapped[int] = mapped_column(primary_key=True)`. **The `id` defines join order.**
   - `group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"))`
   - `user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))`
   - `active: Mapped[bool] = mapped_column(default=True, server_default=true())`. `true` comes from `sqlalchemy`.

### `app/migrations/versions/rev_0002_create_groups.py`

- Docstring `"""create groups and group_members tables\n\nRevision ID: 0002\nRevises: 0001\n"""`.
- `revision: str = "0002"` and `down_revision: str | None = "0001"`. `branch_labels` and `depends_on` as in `rev_0001_create_users.py`.
- `upgrade()`:
  1. `op.create_table("groups", ...)` with `sa.Column("id", sa.Integer(), primary_key=True)` and `sa.Column("name", sa.String(64), nullable=False)`.
  2. `op.create_table("group_members", ...)` with:
     - `sa.Column("id", sa.Integer(), primary_key=True)`
     - `sa.Column("group_id", sa.Integer(), nullable=False)`
     - `sa.Column("user_id", sa.Integer(), nullable=False)`
     - `sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true())`
     - `sa.ForeignKeyConstraint(["group_id"], ["groups.id"], name="fk_group_members_group_id_groups")`
     - `sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_group_members_user_id_users")`
     - `sa.UniqueConstraint("group_id", "user_id", name="uq_group_members_group_user")`
- `downgrade()`: `op.drop_table("group_members")`, then `op.drop_table("groups")`.

### `app/repositories/groups.py`

`class GroupRepository`, constructed with `__init__(self, session: Session) -> None`, which stores `self._session`:
- `create(self, name: str) -> Group`: add, `flush`, return.
- `get(self, group_id: int) -> Group | None`: `self._session.get(Group, group_id)`.
- `get_membership(self, group_id: int, user_id: int) -> GroupMember | None`: `scalars(select(GroupMember).where(GroupMember.group_id == group_id, GroupMember.user_id == user_id)).one_or_none()`.
- `add_member(self, group_id: int, user_id: int) -> GroupMember`: add, `flush`, return.
- `active_member_users(self, group_id: int) -> list[User]`:
  - `select(User).join(GroupMember, GroupMember.user_id == User.id)`
  - `.where(GroupMember.group_id == group_id, GroupMember.active.is_(True))`
  - `.order_by(GroupMember.id)`, then `list(self._session.scalars(...))`.
- `groups_for_user(self, user_id: int) -> list[Group]`:
  - `select(Group).join(GroupMember, GroupMember.group_id == Group.id)`
  - `.where(GroupMember.user_id == user_id, GroupMember.active.is_(True))`
  - `.order_by(Group.id)`, then `list(...)`.

### `app/services/groups.py`

- Errors, all `class X(Exception)` with no members: `GroupNotFoundError`, `UserNotFoundError`, `AlreadyMemberError`.
- `@dataclass(frozen=True, slots=True) class GroupView` with fields `group: Group` and `members: list[User]`. Members are in join order.

`class GroupService`, constructed with `__init__(self, session: Session) -> None`, which stores the session, `self._groups = GroupRepository(session)` and `self._users = UserRepository(session)`.

**`_require_active_member(self, user: User, group_id: int) -> Group`.**
- `group = self._groups.get(group_id)`.
- If `group is None`, raise `GroupNotFoundError(group_id)`.
- `membership = self._groups.get_membership(group_id, user.id)`.
- If `membership is None or not membership.active`, raise `GroupNotFoundError(group_id)`.
- Return `group`.

**`_view(self, group: Group) -> GroupView`.** Returns `GroupView(group=group, members=self._groups.active_member_users(group.id))`.

**`create_group(self, owner: User, name: str) -> GroupView`.** `group = self._groups.create(name)`, then `self._groups.add_member(group.id, owner.id)`, then `self._session.commit()`. Return `self._view(group)`.

**`list_groups(self, user: User) -> list[Group]`.** Returns `self._groups.groups_for_user(user.id)`.

**`get_group(self, user: User, group_id: int) -> GroupView`.** Returns `self._view(self._require_active_member(user, group_id))`.

**`add_member(self, actor: User, group_id: int, username: str) -> GroupView`.**
1. `group = self._require_active_member(actor, group_id)`.
2. `target = self._users.get_by_username(username.lower())`. If it is `None`, raise `UserNotFoundError(username)`.
3. If `self._groups.get_membership(group_id, target.id) is not None`, raise `AlreadyMemberError(username)`. Stage 06 refines this check for inactive members who rejoin.
4. `self._groups.add_member(group_id, target.id)`, then `self._session.commit()`. Return `self._view(group)`.

### `app/api/deps.py`

Append:
- `def get_group_service(session: SessionDep) -> GroupService`: returns `GroupService(session)`.
- `GroupServiceDep = Annotated[GroupService, Depends(get_group_service)]`.

### `app/api/groups.py`

Schemas (Pydantic `BaseModel`):
- `CreateGroupRequest`: `name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]`.
- `AddMemberRequest`: `username: str`.
- `MemberResponse`: `id: int`, `username: str`.
- `GroupSummaryResponse`: `id: int`, `name: str`.
- `GroupDetailResponse`: `id: int`, `name: str`, `members: list[MemberResponse]`.

Helpers:
- `def _detail(view: GroupView) -> GroupDetailResponse`: `id=view.group.id`, `name=view.group.name`, and `members=[MemberResponse(id=u.id, username=u.username) for u in view.members]`.
- `def _group_not_found() -> HTTPException`: returns `HTTPException(status_code=404, detail="group not found")`.

`router = APIRouter(prefix="/groups", tags=["groups"])`.

Endpoints. Every endpoint takes `user: CurrentUserDep, service: GroupServiceDep`.

| Method and path | Status | Response model | Function | Behavior and error mapping |
|-----------------|--------|----------------|----------|----------------------------|
| `POST ""` | 201 | `GroupDetailResponse` | `create_group(body: CreateGroupRequest, …)` | `_detail(service.create_group(user, body.name))` |
| `GET ""` | 200 | `list[GroupSummaryResponse]` | `list_groups(…)` | `[GroupSummaryResponse(id=g.id, name=g.name) for g in service.list_groups(user)]` |
| `GET "/{group_id}"` | 200 | `GroupDetailResponse` | `get_group(group_id: int, …)` | `GroupNotFoundError` → `_group_not_found()` |
| `POST "/{group_id}/members"` | 201 | `GroupDetailResponse` | `add_member(group_id: int, body: AddMemberRequest, …)` | `GroupNotFoundError` → `_group_not_found()`; `UserNotFoundError` → 404 `"user not found"`; `AlreadyMemberError` → 409 `"user is already a member"` |

Raise every mapped error with `from None`.

### `app/main.py`

Add `app.include_router(groups_router, prefix="/api")` after the auth router, importing `router as groups_router` from `app.api.groups`.

### `app/db.py`

Delete line 4 (`import alembic.config`) and change the return annotation of `make_alembic_config` to `-> Config`. No other change.

## 4. Edit recipe, in order

All paths are under `backend/`.

1. `app/db.py`: the import cleanup from section 3.
2. `app/repositories/models.py`: add the naming convention, `Group` and `GroupMember`. Add the needed imports: `ForeignKey`, `MetaData` and `true` from `sqlalchemy`.
3. Create `app/migrations/versions/rev_0002_create_groups.py`.
4. Create `app/repositories/groups.py`, then `app/services/groups.py`.
5. `app/api/deps.py`: append the group-service dependency.
6. Create `app/api/groups.py`. In `app/main.py`, include the router.
7. Create `tests/test_groups.py` and modify `tests/test_migrations.py` from section 6.

## 5. Edge cases

Users are registered in this order: alice (id 1), bob (id 2), carol (id 3).

| Situation | Expected |
|-----------|----------|
| alice `POST /api/groups {"name": "  Flat  "}` | 201 `{"id": 1, "name": "Flat", "members": [{"id": 1, "username": "alice"}]}` |
| Name `""`, `"   "` or `"x"*65` | 422 |
| alice adds `"carol"`, then `"Bob"` | members `[alice(1), carol(3), bob(2)]`: join order, not ID order |
| alice adds `"dave"`, who is not registered | 404 `{"detail": "user not found"}` |
| alice adds `"bob"` twice, or adds `"alice"` | 409 `{"detail": "user is already a member"}` |
| bob (not a member) `GET /api/groups/1` or `POST /api/groups/1/members` | 404 `{"detail": "group not found"}` |
| alice `GET /api/groups/999` | 404 `{"detail": "group not found"}`, identical to the non-member case (AC5) |
| no token on any `/api/groups…` endpoint | 401 `{"detail": "not authenticated"}` |
| bob `GET /api/groups` with no memberships | 200 `[]` |

## 6. Tests

### `tests/test_groups.py`

Imports: `pytest`, `TestClient`, `Settings`, `create_app`, and `httpx2` for typing the response.

Module helper `def _user(client: TestClient, username: str) -> dict[str, str]`:
- Registers `username` with the password `"correct-horse"`.
- Logs in with form data.
- Returns `{"Authorization": f"Bearer {token}"}`.
- Assert status 201 on register and 200 on login inside the helper.

Tests. Unless a test says otherwise, users are created with `_user` in the order alice, bob, carol, and only the users the test needs.

1. **`test_create_group_makes_creator_member`**:
   - alice posts `{"name": "Trip"}`.
   - Assert 201 and `{"id": 1, "name": "Trip", "members": [{"id": 1, "username": "alice"}]}`.
2. **`test_create_group_strips_name`**: `"  Flat  "` gives 201 with `json()["name"] == "Flat"`.
3. **`test_create_group_rejects_invalid_name`**, parametrized on `"name"`:
   - Cases: `""`, `"   "`, `"x" * 65`.
   - Assert 422.
4. **`test_list_groups_shows_only_own_groups`**:
   - alice creates `"A"`, bob creates `"B"`.
   - alice `GET /api/groups` gives `[{"id": 1, "name": "A"}]`.
   - bob gets `[{"id": 2, "name": "B"}]`.
5. **`test_list_groups_empty`**: alice `GET /api/groups` gives 200 `[]`.
6. **`test_add_member_by_username`**:
   - alice creates `"Trip"`, then posts `{"username": "Bob"}` to `/api/groups/1/members`.
   - Assert 201 with members `[{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}]`.
   - Then bob `GET /api/groups/1` gives 200 with the same members.
   - bob `GET /api/groups` gives `[{"id": 1, "name": "Trip"}]`.
7. **`test_members_listed_in_join_order`**:
   - Register alice, bob, carol. alice creates a group, adds `"carol"`, then `"bob"`.
   - Assert the final response's `members == [{"id": 1, "username": "alice"}, {"id": 3, "username": "carol"}, {"id": 2, "username": "bob"}]`.
   - This also closes the stage 02 receipt's order follow-up for member lists.
8. **`test_add_member_unknown_user`**: gives 404 and `{"detail": "user not found"}`.
9. **`test_add_member_rejects_existing_member`**, parametrized on `"username"`:
   - Cases: `"bob"`, `"alice"`.
   - alice creates a group. For the `"bob"` case, add bob once first.
   - Then posting `username` gives 409 and `{"detail": "user is already a member"}`.
   - Implement the setup as: `if username == "bob": add bob first`.
10. **`test_ac5_non_member_gets_404`**, parametrized on `("method", "path", "json_body")`:
    - Cases: `("GET", "/api/groups/1", None)`, `("POST", "/api/groups/1/members", {"username": "carol"})`.
    - alice creates a group; bob and carol are registered.
    - `client.request(method, path, json=json_body, headers=bob_headers)` gives 404 and `{"detail": "group not found"}`.
11. **`test_ac5_missing_group_is_indistinguishable`**: alice `GET /api/groups/999` gives 404 and `{"detail": "group not found"}`.
12. **`test_ac5_groups_require_authentication`**, parametrized on `("method", "path", "json_body")`:
    - Cases: `("GET", "/api/groups", None)`, `("POST", "/api/groups", {"name": "X"})`, `("GET", "/api/groups/1", None)`, `("POST", "/api/groups/1/members", {"username": "bob"})`.
    - With no headers, assert 401 and `{"detail": "not authenticated"}`.
13. **`test_ac8_groups_survive_restart`** (`settings` fixture, no `client` fixture):
    1. `with TestClient(create_app(settings)) as first`: `_user` alice and bob, alice creates `"Trip"` and adds `"bob"`.
    2. `with TestClient(create_app(settings)) as second`: log in alice. Reuse a `_login_headers(client, username)` helper, extracted from `_user`; this is the only allowed refactor.
    3. Assert `GET /api/groups/1` gives 200 with members `[alice(1), bob(2)]`.

### `tests/test_migrations.py`

Modify:
- **`test_migrations_create_tables`**: the expected set becomes `{"users", "groups", "group_members", "alembic_version"}`.
- **`test_migrations_are_idempotent`**: the expected value becomes `["0002"]`.

Add:
14. **`test_migration_0002_preserves_existing_users`**:
    1. `with engine.begin() as c: command.upgrade(make_alembic_config(c), "0001")`.
    2. `with engine.begin() as c: c.execute(text("INSERT INTO users (username, password_hash) VALUES ('legacy', 'h')"))`.
    3. `run_migrations(engine)`.
    4. With `engine.connect() as c`, assert `c.execute(text("SELECT id, username, password_hash FROM users")).all() == [(1, "legacy", "h")]`.
15. **`test_migration_0002_downgrade_keeps_users`**:
    1. `run_migrations(engine)`, then insert the same row.
    2. `with engine.begin() as c: command.downgrade(make_alembic_config(c), "0001")`.
    3. Assert the `users` rows are unchanged, and that `"groups"` and `"group_members"` are not in `inspect(engine).get_table_names()`.

`test_migrations_match_models` stays unchanged and must pass, with no diff.

### Focused checks (Tier 1)

Run in `backend/` and report each exit code:
- `uv run pytest tests -q` (the whole backend suite, because models and migrations change; no coverage)
- `uv run ruff check app tests`
- `uv run ruff format --check app tests`
- `uv run mypy`

## 7. Stop conditions

Stop and report; do not work around:
- `test_migrations_match_models` reports a diff. Paste it verbatim. Do not change the model or the migration.
- Any section 6 assertion fails. Report the case, the actual body and status, and `path:line`.
- mypy or ruff errors that a mechanical change cannot fix. No `type: ignore`, no `noqa`.
- A file outside section 2 is needed, or a new dependency.

Done when: the four checks exit 0, the pytest output has no warnings, and the report is delivered.

## Addendum 05-A (review finding)

**Gap.** Section 6 did not name the type of the parametrized `json_body`. The implementer used `dict[str, Any] | None`, which breaks the AGENTS.md typing invariant: no `Any` without an inline reason.

**Resolved recipe.** Edit only `backend/tests/test_groups.py`:
1. In `test_ac5_non_member_gets_404` and `test_ac5_groups_require_authentication`, change the annotation of `json_body` from `dict[str, Any] | None` to `dict[str, str] | None`. Every request body in those parameter lists has only `str` values.
2. Delete `from typing import Any`, at line 1.

**Checks** (in `backend/`):
- `uv run pytest tests/test_groups.py -q`
- `uv run ruff check tests/test_groups.py`
- `uv run ruff format --check tests/test_groups.py`
- `uv run mypy`

Stop if mypy rejects `dict[str, str] | None`, and report the exact error.

## Acceptance receipt (2026-10-11)

**Review.** Main reviewed the diff against sections 2–6. The models, the migration (with named constraints), the repository queries (join order by `GroupMember.id`), the service check order and the API error mapping all match the spec. One finding: the tests used `dict[str, Any]`, which breaks the AGENTS.md typing invariant. Addendum 05-A sent it back to the same implementer, which replaced it with `dict[str, str]`.

**Implementer Tier 1.** The first pass hit E501 and format errors in 2 files, fixed with `ruff format`. After 05-A, a blank first line was also fixed with `ruff format`. Final exit codes were 0 on all checks.

**Tier 2 gate** (`/gate 05 backend`), with logs in `.logs/05-gate-*.log`. The frontend is unchanged since `9943c99`: `git diff --stat 9943c99 -- frontend` is empty and there are no working-tree changes, so the stage 01 frontend receipt still stands.

| Step | Command | Exit | Summary |
|------|---------|------|---------|
| backend tests | `uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90` | 0 | 174 passed, 0 warnings; coverage 100.00% (491 stmts, 88 branches) |
| backend types | `uv run mypy` | 0 | no issues in 31 source files |
| backend lint | `uv run ruff check .` | 0 | All checks passed |
| backend format | `uv run ruff format --check .` | 0 | 31 files already formatted |

**Accepted deviations:**
- `ruff format` reflows.
- In test 9, bob is registered only in the `"bob"` case.

**Findings and follow-ups:**
- Stage 06 must refine `AlreadyMemberError` so that an inactive member can rejoin.
- The member-order follow-up from the stage 02 receipt is closed by `test_members_listed_in_join_order`.
