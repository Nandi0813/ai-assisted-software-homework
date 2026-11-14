from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.domain.balances import (
    ExpenseEntry,
    PaymentEntry,
    Transfer,
    compute_balances,
    settle_up,
)
from app.domain.money import MoneyError, parse_amount
from app.domain.splits import SplitError, split_equal, split_exact, split_percent
from app.repositories.groups import GroupRepository
from app.repositories.ledger import LedgerRepository, ShareRow
from app.repositories.models import Expense, Payment, User
from app.repositories.users import UserRepository
from app.services.groups import require_active_member


@dataclass(frozen=True, slots=True)
class ShareInput:
    user_id: int
    value: str


@dataclass(frozen=True, slots=True)
class ExpenseInput:
    description: str
    amount: str
    payer_id: int
    split_type: Literal["equal", "exact", "percent"]
    participants: list[int]
    shares: list[ShareInput]


@dataclass(frozen=True, slots=True)
class MemberBalance:
    user_id: int
    username: str
    balance_cents: int
    active: bool


@dataclass(frozen=True, slots=True)
class BalanceView:
    members: list[MemberBalance]
    transfers: list[Transfer]


class ExpenseNotFoundError(Exception):
    pass


class NotExpenseCreatorError(Exception):
    pass


class LedgerValidationError(Exception):
    pass


class LedgerService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._groups = GroupRepository(session)
        self._ledger = LedgerRepository(session)
        self._users = UserRepository(session)

    def _active_order(self, group_id: int) -> dict[int, int]:
        active = [m for m, _ in self._groups.member_rows(group_id) if m.active]
        return {m.user_id: i for i, m in enumerate(active)}

    def _resolve(self, group_id: int, data: ExpenseInput) -> tuple[int, list[ShareRow]]:
        try:
            total = parse_amount(data.amount)
        except MoneyError as e:
            raise LedgerValidationError(str(e)) from None

        order = self._active_order(group_id)
        if data.payer_id not in order:
            raise LedgerValidationError("payer is not a member of this group")

        rows: list[ShareRow]
        if data.split_type == "equal":
            for participant in data.participants:
                if participant not in order:
                    raise LedgerValidationError(
                        f"participant {participant} is not a member of this group"
                    )
            ordered = sorted(data.participants, key=order.__getitem__)
            try:
                split = split_equal(total, ordered)
            except SplitError as e:
                raise LedgerValidationError(str(e)) from None
            rows = [(user_id, cents, None) for user_id, cents in split.items()]
        else:
            seen: set[int] = set()
            for share in data.shares:
                if share.user_id in seen:
                    raise LedgerValidationError(f"duplicate participant: {share.user_id}")
                seen.add(share.user_id)
                if share.user_id not in order:
                    raise LedgerValidationError(
                        f"participant {share.user_id} is not a member of this group"
                    )

            values: dict[int, int] = {}
            for share in sorted(data.shares, key=lambda item: order[item.user_id]):
                try:
                    values[share.user_id] = parse_amount(share.value)
                except MoneyError as e:
                    raise LedgerValidationError(str(e)) from None

            try:
                if data.split_type == "exact":
                    split = split_exact(total, values)
                    rows = [(user_id, cents, None) for user_id, cents in split.items()]
                else:
                    split = split_percent(total, values)
                    rows = [(user_id, split[user_id], values[user_id]) for user_id in split]
            except SplitError as e:
                raise LedgerValidationError(str(e)) from None
        return total, rows

    def create_expense(self, user: User, group_id: int, data: ExpenseInput) -> Expense:
        require_active_member(self._groups, user, group_id)
        total, shares = self._resolve(group_id, data)
        expense = self._ledger.add_expense(
            group_id=group_id,
            payer_id=data.payer_id,
            created_by=user.id,
            description=data.description,
            amount_cents=total,
            split_type=data.split_type,
            shares=shares,
        )
        self._session.commit()
        return expense

    def list_expenses(self, user: User, group_id: int) -> list[Expense]:
        require_active_member(self._groups, user, group_id)
        return self._ledger.list_expenses(group_id)

    def update_expense(
        self, user: User, group_id: int, expense_id: int, data: ExpenseInput
    ) -> Expense:
        require_active_member(self._groups, user, group_id)
        expense = self._ledger.get_expense(group_id, expense_id)
        if expense is None:
            raise ExpenseNotFoundError
        if expense.created_by != user.id:
            raise NotExpenseCreatorError
        total, shares = self._resolve(group_id, data)
        updated = self._ledger.replace_expense(
            expense,
            payer_id=data.payer_id,
            description=data.description,
            amount_cents=total,
            split_type=data.split_type,
            shares=shares,
        )
        self._session.commit()
        return updated

    def delete_expense(self, user: User, group_id: int, expense_id: int) -> None:
        require_active_member(self._groups, user, group_id)
        expense = self._ledger.get_expense(group_id, expense_id)
        if expense is None:
            raise ExpenseNotFoundError
        if expense.created_by != user.id:
            raise NotExpenseCreatorError
        self._ledger.delete_expense(expense)
        self._session.commit()

    def record_payment(
        self, user: User, group_id: int, from_id: int, to_id: int, amount: str
    ) -> Payment:
        require_active_member(self._groups, user, group_id)
        try:
            amount_cents = parse_amount(amount)
        except MoneyError as e:
            raise LedgerValidationError(str(e)) from None
        order = self._active_order(group_id)
        if from_id not in order:
            raise LedgerValidationError(f"user {from_id} is not a member of this group")
        if to_id not in order:
            raise LedgerValidationError(f"user {to_id} is not a member of this group")
        if from_id == to_id:
            raise LedgerValidationError("payment sender and recipient must differ")
        payment = self._ledger.add_payment(
            group_id=group_id,
            from_id=from_id,
            to_id=to_id,
            created_by=user.id,
            amount_cents=amount_cents,
        )
        self._session.commit()
        return payment

    def list_payments(self, user: User, group_id: int) -> list[Payment]:
        require_active_member(self._groups, user, group_id)
        return self._ledger.list_payments(group_id)

    def balances(self, user: User, group_id: int) -> BalanceView:
        require_active_member(self._groups, user, group_id)
        rows = self._groups.member_rows(group_id)
        ids = [member.user_id for member, _ in rows]
        expenses = [
            ExpenseEntry(
                expense.payer_id,
                {share.user_id: share.amount_cents for share in expense.shares},
            )
            for expense in self._ledger.list_expenses(group_id)
        ]
        payments = [
            PaymentEntry(payment.from_id, payment.to_id, payment.amount_cents)
            for payment in self._ledger.list_payments(group_id)
        ]
        balances = compute_balances(ids, expenses, payments)
        members = [
            MemberBalance(
                member.user_id,
                member_user.username,
                balances[member.user_id],
                member.active,
            )
            for member, member_user in rows
            if member.active or balances[member.user_id] != 0
        ]
        return BalanceView(members, settle_up(balances))
