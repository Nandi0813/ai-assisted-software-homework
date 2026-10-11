from datetime import UTC, datetime, timedelta

import httpx2
import jwt
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PASSWORD = "correct-horse"
FUTURE = datetime.now(UTC) + timedelta(hours=1)
PAST = datetime.now(UTC) - timedelta(minutes=1)


def _register(
    client: TestClient, username: str = "alice", password: str = PASSWORD
) -> httpx2.Response:
    return client.post("/api/auth/register", json={"username": username, "password": password})


def _login(
    client: TestClient, username: str = "alice", password: str = PASSWORD
) -> httpx2.Response:
    return client.post("/api/auth/login", data={"username": username, "password": password})


def _token(client: TestClient) -> str:
    _register(client)
    return str(_login(client).json()["access_token"])


def test_register_creates_user(client: TestClient) -> None:
    r = _register(client)
    assert r.status_code == 201
    assert r.json() == {"id": 1, "username": "alice"}


def test_register_normalizes_username_case(client: TestClient) -> None:
    r = _register(client, "Alice")
    assert r.status_code == 201
    assert r.json()["username"] == "alice"
    dup = _register(client, "ALICE")
    assert dup.status_code == 409
    assert dup.json() == {"detail": "username already taken"}


def test_register_rejects_duplicate(client: TestClient) -> None:
    _register(client)
    r = _register(client)
    assert r.status_code == 409
    assert r.json() == {"detail": "username already taken"}


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("ab", PASSWORD),
        ("a" * 33, PASSWORD),
        ("bad name", PASSWORD),
        ("bad-name", PASSWORD),
        ("alice", "short77"),
        ("alice", "x" * 129),
    ],
)
def test_register_rejects_invalid(client: TestClient, username: str, password: str) -> None:
    assert _register(client, username, password).status_code == 422


def test_register_rejects_missing_fields(client: TestClient) -> None:
    assert client.post("/api/auth/register", json={}).status_code == 422


def test_login_returns_bearer_token(client: TestClient) -> None:
    _register(client)
    r = _login(client)
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert isinstance(r.json()["access_token"], str)
    assert r.json()["access_token"] != ""


def test_login_username_is_case_insensitive(client: TestClient) -> None:
    _register(client)
    assert _login(client, "ALICE").status_code == 200


@pytest.mark.parametrize(
    ("username", "password"),
    [("alice", "wrong-password"), ("nobody", PASSWORD)],
)
def test_login_rejects_bad_credentials(client: TestClient, username: str, password: str) -> None:
    _register(client)
    r = _login(client, username, password)
    assert r.status_code == 401
    assert r.json() == {"detail": "incorrect username or password"}
    assert r.headers["www-authenticate"] == "Bearer"


def test_me_returns_current_user(client: TestClient) -> None:
    token = _token(client)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"id": 1, "username": "alice"}


def test_ac5_me_requires_authentication(client: TestClient) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json() == {"detail": "not authenticated"}
    assert r.headers["www-authenticate"] == "Bearer"


def test_ac5_me_rejects_garbage_token(client: TestClient) -> None:
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401
    assert r.json() == {"detail": "not authenticated"}


@pytest.mark.parametrize(
    ("claims", "use_wrong_secret"),
    [
        ({"sub": "1", "exp": FUTURE}, True),
        ({"sub": "1", "exp": PAST}, False),
        ({"sub": "abc", "exp": FUTURE}, False),
        ({"sub": "999", "exp": FUTURE}, False),
        ({"sub": "1"}, False),
    ],
)
def test_ac5_me_rejects_invalid_tokens(
    client: TestClient,
    settings: Settings,
    claims: dict[str, object],
    use_wrong_secret: bool,
) -> None:
    _register(client)
    secret = "wrong-secret-" + "y" * 32 if use_wrong_secret else settings.jwt_secret
    token = jwt.encode(claims, secret, algorithm="HS256")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    assert r.json() == {"detail": "not authenticated"}


def test_ac8_users_survive_restart(settings: Settings) -> None:
    with TestClient(create_app(settings)) as first:
        assert _register(first).status_code == 201
    with TestClient(create_app(settings)) as second:
        assert _login(second).status_code == 200
