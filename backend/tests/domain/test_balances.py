import re

import pytest

from app.domain.balances import (
    BalanceError,
    ExpenseEntry,
    PaymentEntry,
    Transfer,
    compute_balances,
    settle_up,
)
from app.domain.splits import split_equal, split_exact


def _compound_expenses() -> list[ExpenseEntry]:
    return [
        ExpenseEntry(1, split_equal(10000, [1, 2, 3, 4, 5])),
        ExpenseEntry(3, split_equal(2501, [2, 3, 4])),
        ExpenseEntry(5, split_exact(999, {1: 500, 5: 499})),
    ]


def _compound_balances() -> dict[int, int]:
    return compute_balances([1, 2, 3, 4, 5], _compound_expenses(), [])


def test_ac1_balances_after_equal_split() -> None:
    expense = ExpenseEntry(payer_id=1, shares=split_equal(9000, [1, 2, 3]))
    result = compute_balances([1, 2, 3], [expense], [])
    assert result == {1: 6000, 2: -3000, 3: -3000}


def test_ac1_payment_reduces_balances() -> None:
    expense = ExpenseEntry(payer_id=1, shares=split_equal(9000, [1, 2, 3]))
    payment = PaymentEntry(from_id=2, to_id=1, amount_cents=3000)
    result = compute_balances([1, 2, 3], [expense], [payment])
    assert result == {1: 3000, 2: 0, 3: -3000}


def test_balances_without_activity_are_zero() -> None:
    assert compute_balances([1, 2], [], []) == {1: 0, 2: 0}


def test_balances_payer_need_not_participate() -> None:
    expense = ExpenseEntry(1, {2: 500, 3: 500})
    result = compute_balances([1, 2, 3], [expense], [])
    assert result == {1: 1000, 2: -500, 3: -500}


def test_balances_keep_join_order() -> None:
    assert list(compute_balances([3, 1, 2], [], [])) == [3, 1, 2]


def test_balances_always_sum_to_zero() -> None:
    result = _compound_balances()
    assert sum(result.values()) == 0
    assert result == {1: 7500, 2: -2834, 3: -333, 4: -2833, 5: -1500}


@pytest.mark.parametrize(
    ("members", "expenses", "payments", "message"),
    [
        ([1, 1], [], [], "duplicate member: 1"),
        ([1, 2], [ExpenseEntry(9, {1: 100})], [], "unknown member: 9"),
        ([1, 2], [ExpenseEntry(1, {9: 100})], [], "unknown member: 9"),
        ([1, 2], [], [PaymentEntry(9, 1, 100)], "unknown member: 9"),
        ([1, 2], [], [PaymentEntry(1, 9, 100)], "unknown member: 9"),
        ([1, 2], [], [PaymentEntry(1, 1, 100)], "payment sender and recipient must differ"),
        ([1, 2], [], [PaymentEntry(1, 2, 0)], "payment amount must be positive"),
        ([1, 2], [], [PaymentEntry(1, 2, -5)], "payment amount must be positive"),
    ],
)
def test_compute_balances_rejects_invalid(
    members: list[int],
    expenses: list[ExpenseEntry],
    payments: list[PaymentEntry],
    message: str,
) -> None:
    with pytest.raises(BalanceError, match=re.escape(message)):
        compute_balances(members, expenses, payments)


def test_ac6_settle_up_after_equal_split() -> None:
    assert settle_up({1: 6000, 2: -3000, 3: -3000}) == [
        Transfer(2, 1, 3000),
        Transfer(3, 1, 3000),
    ]


def test_settle_up_creditor_tie_goes_to_earliest_joiner() -> None:
    assert settle_up({1: 1000, 2: 1000, 3: -2000}) == [
        Transfer(3, 1, 1000),
        Transfer(3, 2, 1000),
    ]


def test_ac6_settle_up_mixed_balances() -> None:
    result = settle_up({1: 5000, 2: -2000, 3: 3000, 4: -6000})
    assert result == [
        Transfer(4, 1, 5000),
        Transfer(2, 3, 2000),
        Transfer(4, 3, 1000),
    ]
    assert len(result) == 3


def test_ac6_settle_up_compound() -> None:
    assert settle_up(_compound_balances()) == [
        Transfer(2, 1, 2834),
        Transfer(4, 1, 2833),
        Transfer(5, 1, 1500),
        Transfer(3, 1, 333),
    ]


@pytest.mark.parametrize("balances", [{}, {1: 0, 2: 0}])
def test_settle_up_all_settled(balances: dict[int, int]) -> None:
    assert settle_up(balances) == []


def test_settle_up_rejects_non_zero_sum() -> None:
    with pytest.raises(BalanceError, match=re.escape("balances must sum to zero, got 0.50")):
        settle_up({1: 100, 2: -50})


@pytest.mark.parametrize(
    "balances",
    [
        {1: 6000, 2: -3000, 3: -3000},
        {1: 1000, 2: 1000, 3: -2000},
        {1: 5000, 2: -2000, 3: 3000, 4: -6000},
        {1: -1, 2: -1, 3: -1, 4: 3},
        {1: 250, 2: -100, 3: -100, 4: -50},
    ],
)
def test_ac6_recording_transfers_settles_everyone(balances: dict[int, int]) -> None:
    transfers = settle_up(balances)
    nonzero = sum(1 for b in balances.values() if b != 0)
    assert len(transfers) <= nonzero - 1
    assert all(t.amount_cents > 0 for t in transfers)
    after = dict(balances)
    for t in transfers:
        after[t.from_id] += t.amount_cents
        after[t.to_id] -= t.amount_cents
    assert all(v == 0 for v in after.values())


def test_ac6_settling_through_payments_zeroes_compound_balances() -> None:
    balances = _compound_balances()
    payments = [PaymentEntry(t.from_id, t.to_id, t.amount_cents) for t in settle_up(balances)]
    result = compute_balances([1, 2, 3, 4, 5], _compound_expenses(), payments)
    assert all(v == 0 for v in result.values())
