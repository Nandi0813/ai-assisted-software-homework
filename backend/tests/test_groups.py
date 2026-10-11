import httpx2
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PASSWORD = "correct-horse"


def _login_headers(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/api/auth/login", data={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    token = str(response.json()["access_token"])
    return {"Authorization": f"Bearer {token}"}


def _user(client: TestClient, username: str) -> dict[str, str]:
    register: httpx2.Response = client.post(
        "/api/auth/register", json={"username": username, "password": PASSWORD}
    )
    assert register.status_code == 201
    return _login_headers(client, username)


def test_create_group_makes_creator_member(client: TestClient) -> None:
    alice = _user(client, "alice")
    response = client.post("/api/groups", json={"name": "Trip"}, headers=alice)
    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "name": "Trip",
        "members": [{"id": 1, "username": "alice"}],
    }


def test_create_group_strips_name(client: TestClient) -> None:
    alice = _user(client, "alice")
    response = client.post("/api/groups", json={"name": "  Flat  "}, headers=alice)
    assert response.status_code == 201
    assert response.json()["name"] == "Flat"


@pytest.mark.parametrize("name", ["", "   ", "x" * 65])
def test_create_group_rejects_invalid_name(client: TestClient, name: str) -> None:
    alice = _user(client, "alice")
    response = client.post("/api/groups", json={"name": name}, headers=alice)
    assert response.status_code == 422


def test_list_groups_shows_only_own_groups(client: TestClient) -> None:
    alice = _user(client, "alice")
    bob = _user(client, "bob")
    assert client.post("/api/groups", json={"name": "A"}, headers=alice).status_code == 201
    assert client.post("/api/groups", json={"name": "B"}, headers=bob).status_code == 201
    alice_list = client.get("/api/groups", headers=alice)
    assert alice_list.status_code == 200
    assert alice_list.json() == [{"id": 1, "name": "A"}]
    bob_list = client.get("/api/groups", headers=bob)
    assert bob_list.json() == [{"id": 2, "name": "B"}]


def test_list_groups_empty(client: TestClient) -> None:
    alice = _user(client, "alice")
    response = client.get("/api/groups", headers=alice)
    assert response.status_code == 200
    assert response.json() == []


def test_add_member_by_username(client: TestClient) -> None:
    alice = _user(client, "alice")
    bob = _user(client, "bob")
    assert client.post("/api/groups", json={"name": "Trip"}, headers=alice).status_code == 201
    added = client.post("/api/groups/1/members", json={"username": "Bob"}, headers=alice)
    assert added.status_code == 201
    expected_members = [{"id": 1, "username": "alice"}, {"id": 2, "username": "bob"}]
    assert added.json()["members"] == expected_members
    bob_view = client.get("/api/groups/1", headers=bob)
    assert bob_view.status_code == 200
    assert bob_view.json()["members"] == expected_members
    bob_list = client.get("/api/groups", headers=bob)
    assert bob_list.json() == [{"id": 1, "name": "Trip"}]


def test_members_listed_in_join_order(client: TestClient) -> None:
    alice = _user(client, "alice")
    _user(client, "bob")
    _user(client, "carol")
    assert client.post("/api/groups", json={"name": "Trip"}, headers=alice).status_code == 201
    assert (
        client.post("/api/groups/1/members", json={"username": "carol"}, headers=alice).status_code
        == 201
    )
    final = client.post("/api/groups/1/members", json={"username": "bob"}, headers=alice)
    assert final.status_code == 201
    assert final.json()["members"] == [
        {"id": 1, "username": "alice"},
        {"id": 3, "username": "carol"},
        {"id": 2, "username": "bob"},
    ]


def test_add_member_unknown_user(client: TestClient) -> None:
    alice = _user(client, "alice")
    assert client.post("/api/groups", json={"name": "Trip"}, headers=alice).status_code == 201
    response = client.post("/api/groups/1/members", json={"username": "dave"}, headers=alice)
    assert response.status_code == 404
    assert response.json() == {"detail": "user not found"}


@pytest.mark.parametrize("username", ["bob", "alice"])
def test_add_member_rejects_existing_member(client: TestClient, username: str) -> None:
    alice = _user(client, "alice")
    assert client.post("/api/groups", json={"name": "Trip"}, headers=alice).status_code == 201
    if username == "bob":
        _user(client, "bob")
        assert (
            client.post(
                "/api/groups/1/members", json={"username": "bob"}, headers=alice
            ).status_code
            == 201
        )
    response = client.post("/api/groups/1/members", json={"username": username}, headers=alice)
    assert response.status_code == 409
    assert response.json() == {"detail": "user is already a member"}


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("GET", "/api/groups/1", None),
        ("POST", "/api/groups/1/members", {"username": "carol"}),
    ],
)
def test_ac5_non_member_gets_404(
    client: TestClient, method: str, path: str, json_body: dict[str, str] | None
) -> None:
    alice = _user(client, "alice")
    bob = _user(client, "bob")
    _user(client, "carol")
    assert client.post("/api/groups", json={"name": "Trip"}, headers=alice).status_code == 201
    response = client.request(method, path, json=json_body, headers=bob)
    assert response.status_code == 404
    assert response.json() == {"detail": "group not found"}


def test_ac5_missing_group_is_indistinguishable(client: TestClient) -> None:
    alice = _user(client, "alice")
    response = client.get("/api/groups/999", headers=alice)
    assert response.status_code == 404
    assert response.json() == {"detail": "group not found"}


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("GET", "/api/groups", None),
        ("POST", "/api/groups", {"name": "X"}),
        ("GET", "/api/groups/1", None),
        ("POST", "/api/groups/1/members", {"username": "bob"}),
    ],
)
def test_ac5_groups_require_authentication(
    client: TestClient, method: str, path: str, json_body: dict[str, str] | None
) -> None:
    response = client.request(method, path, json=json_body)
    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}


def test_ac8_groups_survive_restart(settings: Settings) -> None:
    with TestClient(create_app(settings)) as first:
        alice = _user(first, "alice")
        _user(first, "bob")
        assert first.post("/api/groups", json={"name": "Trip"}, headers=alice).status_code == 201
        assert (
            first.post("/api/groups/1/members", json={"username": "bob"}, headers=alice).status_code
            == 201
        )
    with TestClient(create_app(settings)) as second:
        alice = _login_headers(second, "alice")
        response = second.get("/api/groups/1", headers=alice)
        assert response.status_code == 200
        assert response.json()["members"] == [
            {"id": 1, "username": "alice"},
            {"id": 2, "username": "bob"},
        ]
