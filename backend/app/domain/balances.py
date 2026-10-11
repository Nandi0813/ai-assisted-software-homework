from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from app.domain.money import format_cents


@dataclass(frozen=True, slots=True)
class ExpenseEntry:
    payer_id: int
    shares: Mapping[int, int]


@dataclass(frozen=True, slots=True)
class PaymentEntry:
    from_id: int
    to_id: int
    amount_cents: int


@dataclass(frozen=True, slots=True)
class Transfer:
    from_id: int
    to_id: int
    amount_cents: int


class BalanceError(ValueError):
    pass


def compute_balances(
    members: Sequence[int],
    expenses: Iterable[ExpenseEntry],
    payments: Iterable[PaymentEntry],
) -> dict[int, int]:
    seen: set[int] = set()
    for m in members:
        if m in seen:
            raise BalanceError(f"duplicate member: {m}")
        seen.add(m)
    balances: dict[int, int] = {m: 0 for m in members}

    for expense in expenses:
        if expense.payer_id not in balances:
            raise BalanceError(f"unknown member: {expense.payer_id}")
        for p in expense.shares:
            if p not in balances:
                raise BalanceError(f"unknown member: {p}")
        total = sum(expense.shares.values())
        balances[expense.payer_id] += total
        for p, share in expense.shares.items():
            balances[p] -= share

    for payment in payments:
        if payment.from_id not in balances:
            raise BalanceError(f"unknown member: {payment.from_id}")
        if payment.to_id not in balances:
            raise BalanceError(f"unknown member: {payment.to_id}")
        if payment.from_id == payment.to_id:
            raise BalanceError("payment sender and recipient must differ")
        if payment.amount_cents < 1:
            raise BalanceError("payment amount must be positive")
        balances[payment.from_id] += payment.amount_cents
        balances[payment.to_id] -= payment.amount_cents

    return balances


def settle_up(balances: Mapping[int, int]) -> list[Transfer]:
    s = sum(balances.values())
    if s != 0:
        raise BalanceError(f"balances must sum to zero, got {format_cents(s)}")

    creditors: dict[int, int] = {p: b for p, b in balances.items() if b > 0}
    debtors: dict[int, int] = {p: -b for p, b in balances.items() if b < 0}

    transfers: list[Transfer] = []
    while creditors:
        c = max(creditors, key=creditors.__getitem__)
        d = max(debtors, key=debtors.__getitem__)
        amount = min(creditors[c], debtors[d])
        transfers.append(Transfer(from_id=d, to_id=c, amount_cents=amount))
        creditors[c] -= amount
        debtors[d] -= amount
        if creditors[c] == 0:
            del creditors[c]
        if debtors[d] == 0:
            del debtors[d]
    return transfers
