from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.models import Expense, ExpenseShare, Payment

ShareRow = tuple[int, int, int | None]


class LedgerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_expense(
        self,
        *,
        group_id: int,
        payer_id: int,
        created_by: int,
        description: str,
        amount_cents: int,
        split_type: str,
        shares: list[ShareRow],
    ) -> Expense:
        expense = Expense(
            group_id=group_id,
            payer_id=payer_id,
            created_by=created_by,
            description=description,
            amount_cents=amount_cents,
            split_type=split_type,
            shares=[ExpenseShare(user_id=u, amount_cents=c, percent_bp=p) for u, c, p in shares],
        )
        self._session.add(expense)
        self._session.flush()
        return expense

    def get_expense(self, group_id: int, expense_id: int) -> Expense | None:
        return self._session.scalars(
            select(Expense).where(Expense.id == expense_id, Expense.group_id == group_id)
        ).one_or_none()

    def list_expenses(self, group_id: int) -> list[Expense]:
        return list(
            self._session.scalars(
                select(Expense).where(Expense.group_id == group_id).order_by(Expense.id)
            )
        )

    def replace_expense(
        self,
        expense: Expense,
        *,
        payer_id: int,
        description: str,
        amount_cents: int,
        split_type: str,
        shares: list[ShareRow],
    ) -> Expense:
        expense.payer_id = payer_id
        expense.description = description
        expense.amount_cents = amount_cents
        expense.split_type = split_type
        expense.shares.clear()
        self._session.flush()
        expense.shares.extend(
            ExpenseShare(user_id=u, amount_cents=c, percent_bp=p) for u, c, p in shares
        )
        self._session.flush()
        return expense

    def delete_expense(self, expense: Expense) -> None:
        self._session.delete(expense)
        self._session.flush()

    def add_payment(
        self,
        *,
        group_id: int,
        from_id: int,
        to_id: int,
        created_by: int,
        amount_cents: int,
    ) -> Payment:
        payment = Payment(
            group_id=group_id,
            from_id=from_id,
            to_id=to_id,
            created_by=created_by,
            amount_cents=amount_cents,
        )
        self._session.add(payment)
        self._session.flush()
        return payment

    def list_payments(self, group_id: int) -> list[Payment]:
        return list(
            self._session.scalars(
                select(Payment).where(Payment.group_id == group_id).order_by(Payment.id)
            )
        )
