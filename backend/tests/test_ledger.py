import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PASSWORD = "correct-horse"
URL = "/api/groups/1"


def _headers(client: TestClient, username: str, register: bool = True) -> dict[str, str]:
    if register:
        response = client.post(
            "/api/auth/register", json={"username": username, "password": PASSWORD}
        )
        assert response.status_code == 201
    response = client.post("/api/auth/login", data={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _setup(client: TestClient) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    alice = _headers(client, "alice")
    bob = _headers(client, "bob")
    carol = _headers(client, "carol")
    created = client.post("/api/groups", json={"name": "Trip"}, headers=alice)
    assert created.status_code == 201
    for username in ("bob", "carol"):
        added = client.post("/api/groups/1/members", json={"username": username}, headers=alice)
        assert added.status_code == 201
    return alice, bob, carol


def _equal(
    amount: str, participants: list[int], payer_id: int = 1, description: str = "Dinner"
) -> dict[str, object]:
    return {
        "description": description,
        "amount": amount,
        "payer_id": payer_id,
        "split": {"type": "equal", "participants": participants},
    }


def _exact(amount: str, shares: list[tuple[int, str]], payer_id: int = 1) -> dict[str, object]:
    return {
        "description": "Dinner",
        "amount": amount,
        "payer_id": payer_id,
        "split": {
            "type": "exact",
            "shares": [{"user_id": user_id, "amount": value} for user_id, value in shares],
        },
    }


def _percent(amount: str, shares: list[tuple[int, str]], payer_id: int = 1) -> dict[str, object]:
    return {
        "description": "Dinner",
        "amount": amount,
        "payer_id": payer_id,
        "split": {
            "type": "percent",
            "shares": [{"user_id": user_id, "percent": value} for user_id, value in shares],
        },
    }


def _balances(client: TestClient, headers: dict[str, str]) -> list[tuple[int, str]]:
    response = client.get(f"{URL}/balances", headers=headers)
    assert response.status_code == 200
    return [(member["user_id"], member["balance"]) for member in response.json()["members"]]


def test_ac1_equal_split_balances(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    response = client.post(f"{URL}/expenses", json=_equal("90.00", [1, 2, 3]), headers=alice)
    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "description": "Dinner",
        "amount": "90.00",
        "payer_id": 1,
        "created_by": 1,
        "split_type": "equal",
        "shares": [
            {"user_id": 1, "amount": "30.00", "percent": None},
            {"user_id": 2, "amount": "30.00", "percent": None},
            {"user_id": 3, "amount": "30.00", "percent": None},
        ],
    }
    assert _balances(client, alice) == [(1, "60.00"), (2, "-30.00"), (3, "-30.00")]


def test_ac2_extra_cent_to_earliest_joiner(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    response = client.post(f"{URL}/expenses", json=_equal("100.00", [3, 2, 1]), headers=alice)
    assert response.status_code == 201
    assert [(share["user_id"], share["amount"]) for share in response.json()["shares"]] == [
        (1, "33.34"),
        (2, "33.33"),
        (3, "33.33"),
    ]


def test_ac2_rounding_follows_join_order_not_user_id(client: TestClient) -> None:
    alice = _headers(client, "alice")
    _headers(client, "bob")
    _headers(client, "carol")
    assert client.post("/api/groups", json={"name": "Trip"}, headers=alice).status_code == 201
    assert (
        client.post("/api/groups/1/members", json={"username": "carol"}, headers=alice).status_code
        == 201
    )
    assert (
        client.post("/api/groups/1/members", json={"username": "bob"}, headers=alice).status_code
        == 201
    )
    response = client.post(f"{URL}/expenses", json=_equal("100.00", [1, 2, 3]), headers=alice)
    assert response.status_code == 201
    assert [(share["user_id"], share["amount"]) for share in response.json()["shares"]] == [
        (1, "33.34"),
        (3, "33.33"),
        (2, "33.33"),
    ]


def test_ac3_exact_split(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    response = client.post(
        f"{URL}/expenses",
        json=_exact("90.00", [(3, "15.00"), (1, "50.00"), (2, "25.00")]),
        headers=alice,
    )
    assert response.status_code == 201
    assert [(share["user_id"], share["amount"]) for share in response.json()["shares"]] == [
        (1, "50.00"),
        (2, "25.00"),
        (3, "15.00"),
    ]
    assert _balances(client, alice) == [(1, "40.00"), (2, "-25.00"), (3, "-15.00")]


def test_ac3_exact_split_sum_mismatch(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    response = client.post(
        f"{URL}/expenses", json=_exact("100.00", [(1, "50.00"), (2, "40.00")]), headers=alice
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "exact shares sum to 90.00, expected 100.00"}
    assert client.get(f"{URL}/expenses", headers=alice).json() == []


def test_ac3_percent_split(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    response = client.post(
        f"{URL}/expenses",
        json=_percent("10.00", [(1, "33.33"), (2, "33.33"), (3, "33.34")]),
        headers=alice,
    )
    assert response.status_code == 201
    assert response.json()["shares"] == [
        {"user_id": 1, "amount": "3.33", "percent": "33.33"},
        {"user_id": 2, "amount": "3.33", "percent": "33.33"},
        {"user_id": 3, "amount": "3.34", "percent": "33.34"},
    ]


def test_ac3_percent_split_must_total_100(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    response = client.post(
        f"{URL}/expenses", json=_percent("10.00", [(1, "50"), (2, "40")]), headers=alice
    )
    assert response.status_code == 422
    assert response.json() == {"detail": "percentages sum to 90.00%, expected 100.00%"}


@pytest.mark.parametrize(
    ("body", "detail"),
    [
        (_equal("0", [1, 2]), "amount must be at least 0.01"),
        (_equal("-5.00", [1, 2]), "invalid amount format: '-5.00'"),
        (_equal("1.234", [1, 2]), "invalid amount format: '1.234'"),
        (_equal("1000000.01", [1, 2]), "amount must not exceed 1000000.00"),
        (_equal("10.00", []), "at least one participant is required"),
        (_equal("10.00", [1, 2], payer_id=99), "payer is not a member of this group"),
        (_equal("10.00", [1, 99]), "participant 99 is not a member of this group"),
        (_equal("10.00", [1, 2, 1]), "duplicate participant: 1"),
        (_exact("10.00", [(1, "5.00"), (1, "5.00")]), "duplicate participant: 1"),
        (_exact("10.00", [(1, "abc"), (2, "5.00")]), "invalid amount format: 'abc'"),
        (
            _percent("10.00", [(1, "100"), (99, "0")]),
            "participant 99 is not a member of this group",
        ),
    ],
)
def test_ac4_rejects_invalid_expense(
    client: TestClient, body: dict[str, object], detail: str
) -> None:
    alice, _, _ = _setup(client)
    response = client.post(f"{URL}/expenses", json=body, headers=alice)
    assert response.status_code == 422
    assert response.json() == {"detail": detail}
    assert client.get(f"{URL}/expenses", headers=alice).json() == []


@pytest.mark.parametrize(
    "body",
    [
        {**_equal("10.00", [1]), "description": ""},
        {**_equal("10.00", [1]), "description": "x" * 201},
        {**_equal("10.00", [1]), "amount": 10},
        {**_equal("10.00", [1]), "split": {"type": "weird", "participants": [1]}},
        {"description": "x", "amount": "1.00", "payer_id": 1},
    ],
)
def test_ac4_rejects_malformed_request(client: TestClient, body: dict[str, object]) -> None:
    alice, _, _ = _setup(client)
    response = client.post(f"{URL}/expenses", json=body, headers=alice)
    assert response.status_code == 422


def test_list_expenses_in_creation_order(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    for body in (_equal("10.00", [1, 2]), _equal("20.00", [2, 3])):
        assert client.post(f"{URL}/expenses", json=body, headers=alice).status_code == 201
    response = client.get(f"{URL}/expenses", headers=alice)
    assert [expense["id"] for expense in response.json()] == [1, 2]
    assert [expense["amount"] for expense in response.json()] == ["10.00", "20.00"]


def test_update_expense_by_creator(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    assert (
        client.post(f"{URL}/expenses", json=_equal("90.00", [1, 2, 3]), headers=alice).status_code
        == 201
    )
    response = client.put(f"{URL}/expenses/1", json=_equal("60.00", [1, 2]), headers=alice)
    assert response.status_code == 200
    assert response.json()["amount"] == "60.00"
    assert [(share["user_id"], share["amount"]) for share in response.json()["shares"]] == [
        (1, "30.00"),
        (2, "30.00"),
    ]
    assert _balances(client, alice) == [(1, "30.00"), (2, "-30.00"), (3, "0.00")]


def test_update_can_change_split_type(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    assert (
        client.post(f"{URL}/expenses", json=_equal("90.00", [1, 2, 3]), headers=alice).status_code
        == 201
    )
    response = client.put(
        f"{URL}/expenses/1", json=_percent("90.00", [(1, "50"), (2, "50")]), headers=alice
    )
    assert response.status_code == 200
    assert response.json()["split_type"] == "percent"
    assert [(share["user_id"], share["amount"]) for share in response.json()["shares"]] == [
        (1, "45.00"),
        (2, "45.00"),
    ]


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_only_creator_can_modify_expense(client: TestClient, method: str) -> None:
    _, bob, _ = _setup(client)
    alice = _headers(client, "alice", register=False)
    assert (
        client.post(f"{URL}/expenses", json=_equal("90.00", [1, 2, 3]), headers=alice).status_code
        == 201
    )
    response = client.request(
        method,
        f"{URL}/expenses/1",
        json=_equal("10.00", [1]) if method == "PUT" else None,
        headers=bob,
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "only the creator can modify this expense"}


def test_delete_expense_by_creator(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    assert (
        client.post(f"{URL}/expenses", json=_equal("90.00", [1, 2, 3]), headers=alice).status_code
        == 201
    )
    assert client.delete(f"{URL}/expenses/1", headers=alice).status_code == 204
    assert client.get(f"{URL}/expenses", headers=alice).json() == []
    assert _balances(client, alice) == [(1, "0.00"), (2, "0.00"), (3, "0.00")]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("PUT", "/api/groups/1/expenses/999"),
        ("DELETE", "/api/groups/1/expenses/999"),
        ("PUT", "/api/groups/2/expenses/1"),
        ("DELETE", "/api/groups/2/expenses/1"),
    ],
)
def test_expense_not_found(client: TestClient, method: str, path: str) -> None:
    alice, _, _ = _setup(client)
    assert (
        client.post(f"{URL}/expenses", json=_equal("90.00", [1, 2, 3]), headers=alice).status_code
        == 201
    )
    assert client.post("/api/groups", json={"name": "Other"}, headers=alice).status_code == 201
    response = client.request(
        method,
        path,
        json=_equal("10.00", [1]) if method == "PUT" else None,
        headers=alice,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "expense not found"}


def test_ac1_payment_reduces_balances(client: TestClient) -> None:
    alice, bob, _ = _setup(client)
    assert (
        client.post(f"{URL}/expenses", json=_equal("90.00", [1, 2, 3]), headers=alice).status_code
        == 201
    )
    response = client.post(
        f"{URL}/payments",
        json={"from_id": 2, "to_id": 1, "amount": "30.00"},
        headers=bob,
    )
    assert response.status_code == 201
    assert response.json() == {
        "id": 1,
        "from_id": 2,
        "to_id": 1,
        "amount": "30.00",
        "created_by": 2,
    }
    assert _balances(client, alice) == [(1, "30.00"), (2, "0.00"), (3, "-30.00")]


@pytest.mark.parametrize(
    ("from_id", "to_id", "amount", "detail"),
    [
        (2, 1, "0.00", "amount must be at least 0.01"),
        (2, 1, "ten", "invalid amount format: 'ten'"),
        (99, 1, "10.00", "user 99 is not a member of this group"),
        (2, 99, "10.00", "user 99 is not a member of this group"),
        (2, 2, "10.00", "payment sender and recipient must differ"),
    ],
)
def test_payment_rejects_invalid(
    client: TestClient, from_id: int, to_id: int, amount: str, detail: str
) -> None:
    alice, _, _ = _setup(client)
    response = client.post(
        f"{URL}/payments",
        json={"from_id": from_id, "to_id": to_id, "amount": amount},
        headers=alice,
    )
    assert response.status_code == 422
    assert response.json() == {"detail": detail}
    assert client.get(f"{URL}/payments", headers=alice).json() == []


def test_list_payments(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    for from_id, amount in ((2, "5.00"), (3, "7.50")):
        response = client.post(
            f"{URL}/payments",
            json={"from_id": from_id, "to_id": 1, "amount": amount},
            headers=alice,
        )
        assert response.status_code == 201
    response = client.get(f"{URL}/payments", headers=alice)
    assert [payment["amount"] for payment in response.json()] == ["5.00", "7.50"]


def test_ac6_settle_up_suggestions(client: TestClient) -> None:
    alice, _, carol = _setup(client)
    assert (
        client.post(f"{URL}/expenses", json=_equal("90.00", [1, 2, 3]), headers=alice).status_code
        == 201
    )
    assert (
        client.post(
            f"{URL}/expenses", json=_equal("30.00", [2, 3], payer_id=3), headers=carol
        ).status_code
        == 201
    )
    response = client.get(f"{URL}/balances", headers=alice)
    assert response.status_code == 200
    assert response.json()["members"] == [
        {"user_id": 1, "username": "alice", "balance": "60.00", "active": True},
        {"user_id": 2, "username": "bob", "balance": "-45.00", "active": True},
        {"user_id": 3, "username": "carol", "balance": "-15.00", "active": True},
    ]
    assert response.json()["transfers"] == [
        {
            "from_id": 2,
            "from_username": "bob",
            "to_id": 1,
            "to_username": "alice",
            "amount": "45.00",
        },
        {
            "from_id": 3,
            "from_username": "carol",
            "to_id": 1,
            "to_username": "alice",
            "amount": "15.00",
        },
    ]


def test_ac6_recording_suggested_transfers_settles_everyone(client: TestClient) -> None:
    alice, _, carol = _setup(client)
    assert (
        client.post(f"{URL}/expenses", json=_equal("90.00", [1, 2, 3]), headers=alice).status_code
        == 201
    )
    assert (
        client.post(
            f"{URL}/expenses", json=_equal("30.00", [2, 3], payer_id=3), headers=carol
        ).status_code
        == 201
    )
    suggested = client.get(f"{URL}/balances", headers=alice).json()["transfers"]
    for transfer in suggested:
        response = client.post(
            f"{URL}/payments",
            json={
                "from_id": transfer["from_id"],
                "to_id": transfer["to_id"],
                "amount": transfer["amount"],
            },
            headers=alice,
        )
        assert response.status_code == 201
    assert _balances(client, alice) == [(1, "0.00"), (2, "0.00"), (3, "0.00")]
    assert client.get(f"{URL}/balances", headers=alice).json()["transfers"] == []


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("GET", "/api/groups/1/expenses", None),
        ("POST", "/api/groups/1/expenses", _equal("10.00", [1])),
        ("PUT", "/api/groups/1/expenses/1", _equal("10.00", [1])),
        ("DELETE", "/api/groups/1/expenses/1", None),
        ("GET", "/api/groups/1/payments", None),
        ("POST", "/api/groups/1/payments", {"from_id": 1, "to_id": 1, "amount": "1.00"}),
        ("GET", "/api/groups/1/balances", None),
    ],
)
def test_ac5_non_member_gets_404(
    client: TestClient,
    method: str,
    path: str,
    json_body: dict[str, object] | None,
) -> None:
    alice = _headers(client, "alice")
    bob = _headers(client, "bob")
    assert client.post("/api/groups", json={"name": "Trip"}, headers=alice).status_code == 201
    assert (
        client.post(f"{URL}/expenses", json=_equal("10.00", [1]), headers=alice).status_code == 201
    )
    response = client.request(method, path, json=json_body, headers=bob)
    assert response.status_code == 404
    assert response.json() == {"detail": "group not found"}


@pytest.mark.parametrize(
    ("method", "path", "json_body"),
    [
        ("GET", "/api/groups/1/expenses", None),
        ("POST", "/api/groups/1/expenses", _equal("10.00", [1])),
        ("PUT", "/api/groups/1/expenses/1", _equal("10.00", [1])),
        ("DELETE", "/api/groups/1/expenses/1", None),
        ("GET", "/api/groups/1/payments", None),
        ("POST", "/api/groups/1/payments", {"from_id": 1, "to_id": 1, "amount": "1.00"}),
        ("GET", "/api/groups/1/balances", None),
    ],
)
def test_ac5_ledger_requires_authentication(
    client: TestClient,
    method: str,
    path: str,
    json_body: dict[str, object] | None,
) -> None:
    response = client.request(method, path, json=json_body)
    assert response.status_code == 401
    assert response.json() == {"detail": "not authenticated"}


def test_ac8_ledger_survives_restart(settings: Settings) -> None:
    with TestClient(create_app(settings)) as first:
        alice, bob, _ = _setup(first)
        assert (
            first.post(
                f"{URL}/expenses", json=_equal("90.00", [1, 2, 3]), headers=alice
            ).status_code
            == 201
        )
        assert (
            first.post(
                f"{URL}/payments",
                json={"from_id": 2, "to_id": 1, "amount": "30.00"},
                headers=bob,
            ).status_code
            == 201
        )
    with TestClient(create_app(settings)) as second:
        alice = _headers(second, "alice", register=False)
        assert _balances(second, alice) == [(1, "30.00"), (2, "0.00"), (3, "-30.00")]
        assert len(second.get(f"{URL}/expenses", headers=alice).json()) == 1
