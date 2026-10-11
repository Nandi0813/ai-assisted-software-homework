---
status: accepted
completion_date: 2026-10-11
implementation_notes: "Accepted: ruff format reflow of 3 files. Minor spec-induced redundancy: app/db.py imports both alembic.config and Config; clean up when db.py is next touched."
---

# 04: Persistence and authentication

## 1. Goal, non-goals

**Goal:**
- SQLite persistence through SQLAlchemy 2, with Alembic migrations that run on startup (D7).
- A `users` table.
- Registration and login, using Argon2 password hashes and an HS256 JWT bearer token (D8).
- A reusable `current user` dependency that returns 401 when authentication is missing or invalid (AC5, first half).
- Proof that users survive an app restart (groundwork for AC8).
- Swap the dev dependency `httpx` for `httpx2` to remove the `StarletteDeprecationWarning` noted in the stage 01 receipt.

**Non-goals:**
- No groups, expenses or payments (stages 05 and 06). No 404 rule for non-members (stage 05).
- No refresh tokens, logout, password change or rate limiting.
- No defence against timing attacks that enumerate usernames; recorded as a known limitation.
- No frontend changes.

## 2. Owned files

All paths are under `backend/`.

| File | Action |
|------|--------|
| `pyproject.toml`, `uv.lock` | modify (dependencies via `uv`, plus one coverage key) |
| `alembic.ini` | create |
| `app/config.py` | create: `Settings`, `load_settings` |
| `app/db.py` | create: `create_db_engine`, `make_alembic_config`, `run_migrations` |
| `app/repositories/__init__.py` | create, empty |
| `app/repositories/models.py` | create: `Base`, `User` |
| `app/repositories/users.py` | create: `UserRepository` |
| `app/services/__init__.py` | create, empty |
| `app/services/auth.py` | create: `AuthError`, `UsernameTakenError`, `AuthService` |
| `app/api/deps.py` | create: `AppContext`, dependencies and aliases, `unauthorized` |
| `app/api/auth.py` | create: schemas and `router` |
| `app/main.py` | modify: `create_app(settings)` and lifespan |
| `app/migrations/env.py` | create |
| `app/migrations/script.py.mako` | create, copied verbatim (see step 4) |
| `app/migrations/versions/rev_0001_create_users.py` | create |
| `tests/conftest.py` | modify: `settings` fixture, and `client` uses it |
| `tests/test_auth.py` | create |
| `tests/test_migrations.py` | create |

**Existing code:**
- `app/main.py:6`: `create_app()` is called by `app/main.py:12` (module-level `app`) and by `tests/conftest.py:11`.
- `app/api/health.py:6`: `router`. Keep it included unchanged.

No `__init__.py` in `app/migrations/` or `app/migrations/versions/`.

## 3. Signatures, types, behavior

### `app/config.py`

- `@dataclass(frozen=True, slots=True) class Settings` with these fields:
  - `database_url: str`
  - `jwt_secret: str`
  - `access_token_minutes: int = 60`
- `def load_settings() -> Settings` reads these environment variables:
  - `database_url`: `SPLITLEDGER_DATABASE_URL`, default `"sqlite:///./splitledger.db"`.
  - `jwt_secret`: `os.environ.get("SPLITLEDGER_JWT_SECRET") or secrets.token_urlsafe(32)`. A random per-process secret is the safe default; tokens then expire when the process restarts.
  - `access_token_minutes`: `int(os.environ.get("SPLITLEDGER_ACCESS_TOKEN_MINUTES", "60"))`.

### `app/db.py`

- `def create_db_engine(url: str) -> Engine`:
  - If `not url.startswith("sqlite")`, raise `ValueError("only SQLite database URLs are supported")`.
  - Otherwise `engine = create_engine(url, connect_args={"check_same_thread": False})`. The cross-thread argument is needed because FastAPI runs sync dependencies and endpoints in a thread pool.
  - Then `event.listen(engine, "connect", _enable_sqlite_foreign_keys)` and return `engine`.
- `def _enable_sqlite_foreign_keys(dbapi_connection: sqlite3.Connection, _connection_record: object) -> None`: open a cursor, execute `"PRAGMA foreign_keys=ON"`, close the cursor.
- `def make_alembic_config(connection: Connection) -> alembic.config.Config`:
  - `cfg = Config()`.
  - `cfg.set_main_option("script_location", str(Path(__file__).parent / "migrations"))`.
  - `cfg.attributes["connection"] = connection`.
  - Return `cfg`.
- `def run_migrations(engine: Engine) -> None`: `with engine.begin() as connection: command.upgrade(make_alembic_config(connection), "head")`.

### `app/repositories/models.py`

- `class Base(DeclarativeBase)`: empty body (`pass`).
- `class User(Base)`:
  - `__tablename__ = "users"`
  - `__table_args__ = (UniqueConstraint("username", name="uq_users_username"),)`
  - `id: Mapped[int] = mapped_column(primary_key=True)`
  - `username: Mapped[str] = mapped_column(String(32))`
  - `password_hash: Mapped[str] = mapped_column(String(255))`

### `app/repositories/users.py`

`class UserRepository`, constructed with `__init__(self, session: Session) -> None`, which stores `self._session`:
- `get_by_id(self, user_id: int) -> User | None`: `self._session.get(User, user_id)`.
- `get_by_username(self, username: str) -> User | None`: `self._session.scalars(select(User).where(User.username == username)).one_or_none()`.
- `add(self, username: str, password_hash: str) -> User`: build a `User`, `session.add`, `session.flush()` so the ID is assigned, then return it.

### `app/services/auth.py`

- Module level: `_password_hash = PasswordHash.recommended()` (pwdlib, Argon2).
- `JWT_ALGORITHM: Final[str] = "HS256"`.
- `class AuthError(Exception)` and `class UsernameTakenError(Exception)`: no extra members.

`class AuthService`, constructed with `__init__(self, session: Session, settings: Settings) -> None`, which stores the session, the settings and `self._users = UserRepository(session)`.

**`register(self, username: str, password: str) -> User`.** `username` is already normalized by the API layer.
- `try`: `user = self._users.add(username, _password_hash.hash(password))`, then `self._session.commit()`.
- `except IntegrityError`: `self._session.rollback()`, then raise `UsernameTakenError(username) from None`.
- Return `user`.

**`authenticate(self, username: str, password: str) -> User`.**
- `user = self._users.get_by_username(username)`.
- If `user is None or not _password_hash.verify(password, user.password_hash)`, raise `AuthError("incorrect username or password")`.
- Return `user`.

**`issue_token(self, user: User) -> str`.**
- `expires = datetime.now(UTC) + timedelta(minutes=self._settings.access_token_minutes)`.
- Return `jwt.encode({"sub": str(user.id), "exp": expires}, self._settings.jwt_secret, algorithm=JWT_ALGORITHM)`.

**`user_from_token(self, token: str) -> User`.**
1. `try`: `payload = jwt.decode(token, self._settings.jwt_secret, algorithms=[JWT_ALGORITHM], options={"require": ["exp", "sub"]})`. `except jwt.InvalidTokenError`: raise `AuthError("invalid token") from None`.
2. `sub = payload["sub"]`. If `not isinstance(sub, str) or not sub.isdigit()`, raise `AuthError("invalid token")`.
3. `user = self._users.get_by_id(int(sub))`. If it is `None`, raise `AuthError("invalid token")`.
4. Return `user`.

### `app/api/deps.py`

- `@dataclass(frozen=True, slots=True) class AppContext` with fields `settings: Settings`, `engine: Engine` and `session_factory: sessionmaker[Session]`.
- `oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)`.
- `def unauthorized(detail: str) -> HTTPException`: returns `HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})`.
- `def get_context(request: Request) -> AppContext`: returns `cast(AppContext, request.app.state.context)`.
- `ContextDep = Annotated[AppContext, Depends(get_context)]`.
- `def get_session(context: ContextDep) -> Iterator[Session]`: `with context.session_factory() as session: yield session`.
- `SessionDep = Annotated[Session, Depends(get_session)]`.
- `def get_auth_service(session: SessionDep, context: ContextDep) -> AuthService`: returns `AuthService(session, context.settings)`.
- `AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]`.
- `def get_current_user(token: Annotated[str | None, Depends(oauth2_scheme)], service: AuthServiceDep) -> User`:
  - If `token is None`, raise `unauthorized("not authenticated")`.
  - `try`: return `service.user_from_token(token)`.
  - `except AuthError`: raise `unauthorized("not authenticated") from None`.
- `CurrentUserDep = Annotated[User, Depends(get_current_user)]`.

### `app/api/auth.py`

- `_USERNAME_RE = re.compile(r"[a-z0-9_]{3,32}")`.
- `def _normalize_username(value: str) -> str`:
  - `lowered = value.lower()`.
  - If `_USERNAME_RE.fullmatch(lowered) is None`, raise `ValueError("username must be 3-32 characters of letters, digits or underscore")`.
  - Return `lowered`.
- `Username = Annotated[str, AfterValidator(_normalize_username)]`.
- `Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]`.
- `class RegisterRequest(BaseModel)`: `username: Username`, `password: Password`.
- `class UserResponse(BaseModel)`: `id: int`, `username: str`.
- `class TokenResponse(BaseModel)`: `access_token: str`, `token_type: Literal["bearer"]`.
- `router = APIRouter(prefix="/auth", tags=["auth"])`.

Endpoints:
1. **`POST /register`**: `status_code=201`, `response_model=UserResponse`. `def register(body: RegisterRequest, service: AuthServiceDep) -> UserResponse`.
   - Calls `service.register(body.username, body.password)`.
   - On `UsernameTakenError`, raises `HTTPException(status_code=409, detail="username already taken") from None`.
   - Returns `UserResponse(id=user.id, username=user.username)`.
2. **`POST /login`**: `response_model=TokenResponse`. `def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], service: AuthServiceDep) -> TokenResponse`.
   - Calls `service.authenticate(form.username.lower(), form.password)`.
   - On `AuthError`, raises `unauthorized("incorrect username or password") from None`.
   - Returns `TokenResponse(access_token=service.issue_token(user), token_type="bearer")`.
3. **`GET /me`**: `response_model=UserResponse`. `def me(user: CurrentUserDep) -> UserResponse`: returns the user's ID and username.

### `app/main.py`

`def create_app(settings: Settings | None = None) -> FastAPI`:
1. `resolved = settings if settings is not None else load_settings()`.
2. `engine = create_db_engine(resolved.database_url)`.
3. `context = AppContext(settings=resolved, engine=engine, session_factory=sessionmaker(bind=engine, expire_on_commit=False))`.
4. Define an inner `lifespan`, decorated with `@asynccontextmanager`: `async def lifespan(_app: FastAPI) -> AsyncIterator[None]`. It calls `run_migrations(engine)`, then `yield`, then `engine.dispose()`.
5. `app = FastAPI(title="SplitLedger API", version="0.1.0", lifespan=lifespan)`, then `app.state.context = context`.
6. Include `health_router` and `auth_router`, both with `prefix="/api"`. Return `app`.

Module-level `app = create_app()` is unchanged. Creating the engine is lazy, so importing the module does not touch the disk.

### `app/migrations/env.py`

- Imports: `cast` from `typing`, `context` from `alembic`, `Connection` from `sqlalchemy.engine`, `create_db_engine` from `app.db`, and `Base` from `app.repositories.models`.
- `def _run(connection: Connection) -> None`:
  - `context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)`.
  - Then `with context.begin_transaction(): context.run_migrations()`.
- Module body:
  - `connection = cast("Connection | None", context.config.attributes.get("connection"))`.
  - If `connection is None` (the CLI path):
    - `url = context.config.get_main_option("sqlalchemy.url")`. If `url is None`, raise `RuntimeError("sqlalchemy.url is not configured")`.
    - `engine = create_db_engine(url)`, then `with engine.begin() as conn: _run(conn)`, then `engine.dispose()`.
  - Else: `_run(connection)`.

### `app/migrations/versions/rev_0001_create_users.py`

- Module docstring: `"""create users table\n\nRevision ID: 0001\nRevises:\n"""`.
- Module variables:
  - `revision: str = "0001"`
  - `down_revision: str | None = None`
  - `branch_labels: str | Sequence[str] | None = None`
  - `depends_on: str | Sequence[str] | None = None`
- `upgrade() -> None`: `op.create_table("users", ...)` with these columns and constraint:
  - `sa.Column("id", sa.Integer(), primary_key=True)`
  - `sa.Column("username", sa.String(32), nullable=False)`
  - `sa.Column("password_hash", sa.String(255), nullable=False)`
  - `sa.UniqueConstraint("username", name="uq_users_username")`
- `downgrade() -> None`: `op.drop_table("users")`.

### `alembic.ini`

Contains only an `[alembic]` section with two keys:
- `script_location = %(here)s/app/migrations`
- `sqlalchemy.url = sqlite:///./splitledger.db`

There are no logging sections, and `env.py` does not call `fileConfig`.

## 4. Edit recipe, in order

Run in `backend/`.

1. `uv remove --dev httpx`, then `uv add --dev httpx2`, then `uv add sqlalchemy alembic "pwdlib[argon2]" pyjwt python-multipart`.
2. In `pyproject.toml`, add `omit = ["app/migrations/env.py"]` to `[tool.coverage.run]`. `env.py` is Alembic glue, and its CLI branch is not run by tests.
3. Create `alembic.ini`, `app/config.py`, `app/db.py`, `app/repositories/{__init__,models,users}.py` and `app/services/{__init__,auth}.py` from section 3.
4. Create `app/migrations/script.py.mako` by copying `.venv/lib/python3.14/site-packages/alembic/templates/generic/script.py.mako` byte for byte. Then create `app/migrations/env.py` and `app/migrations/versions/rev_0001_create_users.py`.
5. Create `app/api/deps.py` and `app/api/auth.py`, then modify `app/main.py`, all from section 3.
6. Modify `tests/conftest.py` and create `tests/test_auth.py` and `tests/test_migrations.py` from section 6.

## 5. Edge cases

| Input | Expected |
|-------|----------|
| Register `{"username": "Alice", "password": "correct-horse"}` | 201 `{"id": 1, "username": "alice"}` |
| Register `"ALICE"` after `"Alice"` | 409 `{"detail": "username already taken"}` |
| Register username `"ab"`, `"a"*33`, `"bad name"` or `"bad-name"` | 422 |
| Register password of 7 or 129 characters | 422 |
| Login form `username=ALICE` with the correct password | 200, `token_type` `"bearer"` |
| Login with the wrong password, or an unknown user | 401 `{"detail": "incorrect username or password"}`, header `WWW-Authenticate: Bearer` |
| `GET /api/auth/me` with no `Authorization` header | 401 `{"detail": "not authenticated"}`, header `WWW-Authenticate: Bearer` (AC5) |
| `/me` with a garbage, wrong-secret, expired, non-numeric-`sub`, unknown-user or no-`exp` token | 401 `{"detail": "not authenticated"}` |
| User registered, app recreated on the same DB file, then login | 200 (AC8 groundwork) |
| `create_db_engine("postgresql://u@h/db")` | `ValueError("only SQLite database URLs are supported")` |

## 6. Tests

### `tests/conftest.py`

Replace the existing contents with:
- Fixture `settings(tmp_path: Path) -> Settings`: returns `Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}", jwt_secret="test-secret-" + "x" * 32, access_token_minutes=60)`. The 44-character secret avoids PyJWT's short-key warning.
- Fixture `client(settings: Settings) -> Iterator[TestClient]`: `with TestClient(create_app(settings)) as test_client: yield test_client`.

`tests/test_health.py` stays unchanged and must still pass.

### `tests/test_auth.py`

Imports:
- `datetime`, `timedelta` and `UTC` from `datetime`;
- `jwt`, `pytest`, and `TestClient` from `fastapi.testclient`;
- `httpx2` (only for the `Response` type: `httpx2.Response`);
- `Settings` from `app.config`, and `create_app` from `app.main`.

Module-level helpers:
- `PASSWORD = "correct-horse"`.
- `def _register(client: TestClient, username: str = "alice", password: str = PASSWORD) -> httpx2.Response`: `client.post("/api/auth/register", json={"username": username, "password": password})`.
- `def _login(client: TestClient, username: str = "alice", password: str = PASSWORD) -> httpx2.Response`: `client.post("/api/auth/login", data={"username": username, "password": password})`.
- `def _token(client: TestClient) -> str`: registers and logs in with the defaults, then returns `str(_login(...).json()["access_token"])`. Call `_register` then `_login`.

Tests:
1. **`test_register_creates_user`**: `_register(client)` gives status 201 and `.json() == {"id": 1, "username": "alice"}`.
2. **`test_register_normalizes_username_case`**:
   - `_register(client, "Alice")` gives 201 with `username == "alice"`.
   - Then `_register(client, "ALICE")` gives 409 and `.json() == {"detail": "username already taken"}`.
3. **`test_register_rejects_duplicate`**: `_register` twice. The second gives 409 with the same body as test 2.
4. **`test_register_rejects_invalid`**, parametrized on `("username", "password")`:
   - `("ab", PASSWORD)`, `("a" * 33, PASSWORD)`, `("bad name", PASSWORD)`, `("bad-name", PASSWORD)`, `("alice", "short77")`, `("alice", "x" * 129)`.
   - Assert `_register(client, username, password).status_code == 422`.
5. **`test_register_rejects_missing_fields`**: `client.post("/api/auth/register", json={}).status_code == 422`.
6. **`test_login_returns_bearer_token`**:
   - `_register(client)`, then `r = _login(client)`.
   - Assert `r.status_code == 200`, `r.json()["token_type"] == "bearer"`, and `r.json()["access_token"]` is a non-empty `str`.
7. **`test_login_username_is_case_insensitive`**: `_register(client)`, then `_login(client, "ALICE").status_code == 200`.
8. **`test_login_rejects_bad_credentials`**, parametrized on `("username", "password")`:
   - Cases: `("alice", "wrong-password")`, `("nobody", PASSWORD)`.
   - After `_register(client)`, assert:
     - status 401;
     - `.json() == {"detail": "incorrect username or password"}`;
     - `r.headers["www-authenticate"] == "Bearer"`.
9. **`test_me_returns_current_user`**:
   - `token = _token(client)`.
   - `client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})` gives 200 and `{"id": 1, "username": "alice"}`.
10. **`test_ac5_me_requires_authentication`**: `client.get("/api/auth/me")` gives:
    - 401;
    - `{"detail": "not authenticated"}`;
    - header `www-authenticate == "Bearer"`.
11. **`test_ac5_me_rejects_garbage_token`**: `Authorization: Bearer garbage` gives 401 and `{"detail": "not authenticated"}`.
12. **`test_ac5_me_rejects_invalid_tokens`**, parametrized on `("claims", "use_wrong_secret")`. Let `future = datetime.now(UTC) + timedelta(hours=1)` and `past = datetime.now(UTC) - timedelta(minutes=1)`, computed at module level. Cases:
    - `({"sub": "1", "exp": future}, True)`: wrong secret.
    - `({"sub": "1", "exp": past}, False)`: expired.
    - `({"sub": "abc", "exp": future}, False)`: non-numeric `sub`.
    - `({"sub": "999", "exp": future}, False)`: unknown user.
    - `({"sub": "1"}, False)`: missing `exp`.

    Steps: `_register(client)`. The secret is `"wrong-secret-" + "y" * 32` if `use_wrong_secret` is true, else `settings.jwt_secret`; the test requests the `settings` fixture. `token = jwt.encode(claims, secret, algorithm="HS256")`. Assert `GET /api/auth/me` with that bearer token gives 401 and `{"detail": "not authenticated"}`. Type `claims` as `dict[str, object]`.
13. **`test_ac8_users_survive_restart`**:
    - `with TestClient(create_app(settings)) as first: assert _register(first).status_code == 201`.
    - `with TestClient(create_app(settings)) as second: assert _login(second).status_code == 200`.

### `tests/test_migrations.py`

Imports:
- `Iterator` from `collections.abc`, `Path` from `pathlib`, and `pytest`;
- from alembic: `command`, `compare_metadata` from `alembic.autogenerate`, and `MigrationContext` from `alembic.runtime.migration`;
- from sqlalchemy: `Engine`, `inspect` and `text`;
- `create_db_engine`, `make_alembic_config` and `run_migrations` from `app.db`, and `Base` from `app.repositories.models`.

Fixture `engine(tmp_path: Path) -> Iterator[Engine]`: `e = create_db_engine(f"sqlite:///{tmp_path / 'm.db'}")`, `yield e`, then `e.dispose()`.

Tests:
1. **`test_migrations_create_tables`**: `run_migrations(engine)`, then assert `{"users", "alembic_version"} <= set(inspect(engine).get_table_names())`.
2. **`test_migrations_are_idempotent`**:
   - Call `run_migrations(engine)` twice.
   - With `engine.connect() as c`, assert `c.execute(text("SELECT version_num FROM alembic_version")).scalars().all() == ["0001"]`.
3. **`test_migrations_match_models`**:
   - `run_migrations(engine)`.
   - With `engine.connect() as c`, assert `compare_metadata(MigrationContext.configure(c), Base.metadata) == []`.
4. **`test_migration_downgrade_to_base`**:
   - `run_migrations(engine)`.
   - With `engine.begin() as c`, call `command.downgrade(make_alembic_config(c), "base")`.
   - Assert `"users" not in inspect(engine).get_table_names()`.
5. **`test_sqlite_foreign_keys_enabled`**: with `engine.connect() as c`, assert `c.execute(text("PRAGMA foreign_keys")).scalar() == 1`.
6. **`test_create_db_engine_rejects_non_sqlite`**: `create_db_engine("postgresql://u@h/db")` raises `ValueError` with `match="only SQLite database URLs are supported"`.

### Focused checks (Tier 1)

Run in `backend/` and report each exit code:
- `uv run pytest tests -q`. This is the whole backend suite, which is allowed here because the conftest change affects every test. Still no coverage run.
- `uv run ruff check app tests`
- `uv run ruff format --check app tests`
- `uv run mypy`

## 7. Stop conditions

Stop and report; do not work around:
- `uv add` or `uv remove` fails, or `StarletteDeprecationWarning` still appears after step 1.
- `test_migrations_match_models` reports a non-empty diff. Paste the diff verbatim. Do not change the model or the migration to make it pass.
- mypy reports errors in `app/migrations/*` or in third-party stubs that a mechanical annotation cannot fix. Do not add `# type: ignore` and do not exclude files.
- Any assertion in section 6 fails, any file outside section 2 is needed, or an extra dependency is needed.

Done when: all files in section 2 are in place, the four focused checks exit 0 with no `StarletteDeprecationWarning` in the pytest output, and the report is delivered.

## 8. Known limitations (for `docs/`, not for the implementer)

- Login for an unknown username skips password verification, so response time can reveal whether a username exists. This is acceptable for the coursework scope.
- The default JWT secret is random per process, so a restart logs everyone out unless `SPLITLEDGER_JWT_SECRET` is set.

## Acceptance receipt (2026-10-11)

Main reviewed the diff against sections 2–6. The signatures, messages, status codes, check order and tests match the spec. `script.py.mako` is byte-identical to Alembic's generic template, checked with `cmp`. `compare_metadata` reports no diff.

The implementer's Tier 1 first pass failed on 4 E501 errors (lines too long). It fixed them with `ruff format`, and the final pass exited 0 on all four checks. Main then ran the backend Tier 2 gate. Logs are in `.logs/04-gate-*.log`. Frontend inputs are unchanged, so the stage 01 receipt still stands.

| Step | Command | Exit | Summary |
|------|---------|------|---------|
| backend tests | `uv run pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90` | 0 | 152 passed, **0 warnings**; coverage 100.00% (351 stmts, 80 branches; `app/migrations/env.py` omitted) |
| backend types | `uv run mypy` | 0 | no issues in 26 source files |
| backend lint | `uv run ruff check .` | 0 | All checks passed |
| backend format | `uv run ruff format --check .` | 0 | 26 files already formatted |

**Resolved:** the `StarletteDeprecationWarning` noted in the stage 01 receipt is gone after the `httpx` → `httpx2` swap. The warning count in the gate log is 0.

**Accepted deviations:** `ruff format` line wrapping in `app/db.py`, `tests/test_auth.py` and `tests/test_migrations.py`.

**Minor finding, caused by the spec:** `app/db.py` imports both `alembic.config` and `Config` from it. This is redundant but harmless; clean it up the next time `db.py` changes.

**Known limitations** (section 8): login timing can reveal whether a username exists, and the per-process random JWT secret logs everyone out on restart unless `SPLITLEDGER_JWT_SECRET` is set.
