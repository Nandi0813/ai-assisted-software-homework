import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

PASSWORD = "correct-horse"
URL = "/api/groups/1"


def _headers(client: TestClient, username: str, register: bool = True) -> dict[str, str]:
    if register:
        registered = client.post(
            "/api/auth/register", json={"username": username, "password": PASSWORD}
        )
        assert registered.status_code == 201
    response = client.post("/api/auth/login", data={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    token = str(response.json()["access_token"])
    return {"Authorization": f"Bearer {token}"}


def _setup(client: TestClient) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    alice = _headers(client, "alice")
    bob = _headers(client, "bob")
    carol = _headers(client, "carol")
    created = client.post("/api/groups", json={"name": "Trip"}, headers=alice)
    assert created.status_code == 201
    for username in ("bob", "carol"):
        added = client.post(f"{URL}/members", json={"username": username}, headers=alice)
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
            "shares": [{"user_id": u, "amount": a} for u, a in shares],
        },
    }


def _percent(amount: str, shares: list[tuple[int, str]], payer_id: int = 1) -> dict[str, object]:
    return {
        "description": "Dinner",
        "amount": amount,
        "payer_id": payer_id,
        "split": {
            "type": "percent",
            "shares": [{"user_id": u, "percent": p} for u, p in shares],
        },
    }


def _balances(client: TestClient, headers: dict[str, str]) -> list[tuple[int, str]]:
    response = client.get(f"{URL}/balances", headers=headers)
    assert response.status_code == 200
    body = response.json()
    return [(m["user_id"], m["balance"]) for m in body["members"]]


#### Expenses and balances


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
    body = response.json()
    assert [(s["user_id"], s["amount"]) for s in body["shares"]] == [
        (1, "33.34"),
        (2, "33.33"),
        (3, "33.33"),
    ]


def test_ac2_rounding_follows_join_order_not_user_id(client: TestClient) -> None:
    alice = _headers(client, "alice")
    _headers(client, "bob")
    _headers(client, "carol")
    created = client.post("/api/groups", json={"name": "Trip"}, headers=alice)
    assert created.status_code == 201
    added_carol = client.post(f"{URL}/members", json={"username": "carol"}, headers=alice)
    assert added_carol.status_code == 201
    added_bob = client.post(f"{URL}/members", json={"username": "bob"}, headers=alice)
    assert added_bob.status_code == 201
    response = client.post(f"{URL}/expenses", json=_equal("100.00", [1, 2, 3]), headers=alice)
    assert response.status_code == 201
    assert [(s["user_id"], s["amount"]) for s in response.json()["shares"]] == [
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
    assert [(s["user_id"], s["amount"]) for s in response.json()["shares"]] == [
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
    listed = client.get(f"{URL}/expenses", headers=alice)
    assert listed.status_code == 200
    assert listed.json() == []


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
    listed = client.get(f"{URL}/expenses", headers=alice)
    assert listed.json() == []


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
    assert (
        client.post(f"{URL}/expenses", json=_equal("10.00", [1, 2]), headers=alice).status_code
        == 201
    )
    assert (
        client.post(f"{URL}/expenses", json=_equal("20.00", [2, 3]), headers=alice).status_code
        == 201
    )
    listed = client.get(f"{URL}/expenses", headers=alice)
    assert listed.status_code == 200
    body = listed.json()
    assert [e["id"] for e in body] == [1, 2]
    assert [e["amount"] for e in body] == ["10.00", "20.00"]


def test_update_expense_by_creator(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    assert (
        client.post(f"{URL}/expenses", json=_equal("90.00", [1, 2, 3]), headers=alice).status_code
        == 201
    )
    response = client.put(f"{URL}/expenses/1", json=_equal("60.00", [1, 2]), headers=alice)
    assert response.status_code == 200
    body = response.json()
    assert [(s["user_id"], s["amount"]) for s in body["shares"]] == [(1, "30.00"), (2, "30.00")]
    assert body["amount"] == "60.00"
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
    body = response.json()
    assert body["split_type"] == "percent"
    assert [(s["user_id"], s["amount"]) for s in body["shares"]] == [(1, "45.00"), (2, "45.00")]


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_only_creator_can_modify_expense(client: TestClient, method: str) -> None:
    alice, bob, _ = _setup(client)
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
    response = client.delete(f"{URL}/expenses/1", headers=alice)
    assert response.status_code == 204
    listed = client.get(f"{URL}/expenses", headers=alice)
    assert listed.json() == []
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
    created = client.post("/api/groups", json={"name": "Other"}, headers=alice)
    assert created.status_code == 201
    response = client.request(
        method,
        path,
        json=_equal("10.00", [1]) if method == "PUT" else None,
        headers=alice,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "expense not found"}


#### Payments and settle-up


def test_ac1_payment_reduces_balances(client: TestClient) -> None:
    alice, bob, _ = _setup(client)
    assert (
        client.post(f"{URL}/expenses", json=_equal("90.00", [1, 2, 3]), headers=alice).status_code
        == 201
    )
    response = client.post(
        f"{URL}/payments", json={"from_id": 2, "to_id": 1, "amount": "30.00"}, headers=bob
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
    listed = client.get(f"{URL}/payments", headers=alice)
    assert listed.json() == []


def test_list_payments(client: TestClient) -> None:
    alice, _, _ = _setup(client)
    first = client.post(
        f"{URL}/payments", json={"from_id": 2, "to_id": 1, "amount": "5.00"}, headers=alice
    )
    assert first.status_code == 201
    second = client.post(
        f"{URL}/payments", json={"from_id": 3, "to_id": 1, "amount": "7.50"}, headers=alice
    )
    assert second.status_code == 201
    listed = client.get(f"{URL}/payments", headers=alice)
    assert listed.status_code == 200
    assert [p["amount"] for p in listed.json()] == ["5.00", "7.50"]


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
    body = response.json()
    assert body["members"] == [
        {"user_id": 1, "username": "alice", "balance": "60.00", "active": True},
        {"user_id": 2, "username": "bob", "balance": "-45.00", "active": True},
        {"user_id": 3, "username": "carol", "balance": "-15.00", "active": True},
    ]
    assert body["transfers"] == [
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
    for t in suggested:
        paid = client.post(
            f"{URL}/payments",
            json={"from_id": t["from_id"], "to_id": t["to_id"], "amount": t["amount"]},
            headers=alice,
        )
        assert paid.status_code == 201
    assert _balances(client, alice) == [(1, "0.00"), (2, "0.00"), (3, "0.00")]
    assert client.get(f"{URL}/balances", headers=alice).json()["transfers"] == []


#### Access control and persistence


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
    created = client.post("/api/groups", json={"name": "Trip"}, headers=alice)
    assert created.status_code == 201
    posted = client.post(f"{URL}/expenses", json=_equal("10.00", [1]), headers=alice)
    assert posted.status_code == 201
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
                f"{URL}/payments", json={"from_id": 2, "to_id": 1, "amount": "30.00"}, headers=bob
            ).status_code
            == 201
        )
    with TestClient(create_app(settings)) as second:
        alice = _headers(second, "alice", register=False)
        assert _balances(second, alice) == [(1, "30.00"), (2, "0.00"), (3, "-30.00")]
        listed = second.get(f"{URL}/expenses", headers=alice)
        assert listed.status_code == 200
        assert len(listed.json()) == 1
