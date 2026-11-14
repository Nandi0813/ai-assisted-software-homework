from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, StringConstraints

from app.api.deps import CurrentUserDep, LedgerServiceDep
from app.domain.money import format_cents
from app.repositories.models import Expense, Payment
from app.services.groups import GroupNotFoundError
from app.services.ledger import (
    BalanceView,
    ExpenseInput,
    ExpenseNotFoundError,
    LedgerValidationError,
    NotExpenseCreatorError,
    ShareInput,
)

Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class EqualSplit(BaseModel):
    type: Literal["equal"]
    participants: list[int]


class ExactShareIn(BaseModel):
    user_id: int
    amount: str


class ExactSplit(BaseModel):
    type: Literal["exact"]
    shares: list[ExactShareIn]


class PercentShareIn(BaseModel):
    user_id: int
    percent: str


class PercentSplit(BaseModel):
    type: Literal["percent"]
    shares: list[PercentShareIn]


Split = Annotated[EqualSplit | ExactSplit | PercentSplit, Field(discriminator="type")]


class ExpenseRequest(BaseModel):
    description: Description
    amount: str
    payer_id: int
    split: Split


class PaymentRequest(BaseModel):
    from_id: int
    to_id: int
    amount: str


class ShareOut(BaseModel):
    user_id: int
    amount: str
    percent: str | None


class ExpenseResponse(BaseModel):
    id: int
    description: str
    amount: str
    payer_id: int
    created_by: int
    split_type: str
    shares: list[ShareOut]


class PaymentResponse(BaseModel):
    id: int
    from_id: int
    to_id: int
    amount: str
    created_by: int


class MemberBalanceOut(BaseModel):
    user_id: int
    username: str
    balance: str
    active: bool


class TransferOut(BaseModel):
    from_id: int
    from_username: str
    to_id: int
    to_username: str
    amount: str


class BalancesResponse(BaseModel):
    members: list[MemberBalanceOut]
    transfers: list[TransferOut]


def _to_input(body: ExpenseRequest) -> ExpenseInput:
    split = body.split
    if isinstance(split, EqualSplit):
        participants = list(split.participants)
        shares: list[ShareInput] = []
    elif isinstance(split, ExactSplit):
        participants = []
        shares = [ShareInput(share.user_id, share.amount) for share in split.shares]
    else:
        participants = []
        shares = [ShareInput(share.user_id, share.percent) for share in split.shares]
    return ExpenseInput(
        description=body.description,
        amount=body.amount,
        payer_id=body.payer_id,
        split_type=split.type,
        participants=participants,
        shares=shares,
    )


def _expense_out(expense: Expense) -> ExpenseResponse:
    return ExpenseResponse(
        id=expense.id,
        description=expense.description,
        amount=format_cents(expense.amount_cents),
        payer_id=expense.payer_id,
        created_by=expense.created_by,
        split_type=expense.split_type,
        shares=[
            ShareOut(
                user_id=share.user_id,
                amount=format_cents(share.amount_cents),
                percent=format_cents(share.percent_bp) if share.percent_bp is not None else None,
            )
            for share in expense.shares
        ],
    )


def _payment_out(payment: Payment) -> PaymentResponse:
    return PaymentResponse(
        id=payment.id,
        from_id=payment.from_id,
        to_id=payment.to_id,
        amount=format_cents(payment.amount_cents),
        created_by=payment.created_by,
    )


def _balances_out(view: BalanceView) -> BalancesResponse:
    names = {member.user_id: member.username for member in view.members}
    return BalancesResponse(
        members=[
            MemberBalanceOut(
                user_id=member.user_id,
                username=member.username,
                balance=format_cents(member.balance_cents),
                active=member.active,
            )
            for member in view.members
        ],
        transfers=[
            TransferOut(
                from_id=transfer.from_id,
                from_username=names[transfer.from_id],
                to_id=transfer.to_id,
                to_username=names[transfer.to_id],
                amount=format_cents(transfer.amount_cents),
            )
            for transfer in view.transfers
        ],
    )


@contextmanager
def _ledger_errors() -> Iterator[None]:
    try:
        yield
    except GroupNotFoundError:
        raise HTTPException(status_code=404, detail="group not found") from None
    except ExpenseNotFoundError:
        raise HTTPException(status_code=404, detail="expense not found") from None
    except NotExpenseCreatorError:
        raise HTTPException(
            status_code=403, detail="only the creator can modify this expense"
        ) from None
    except LedgerValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None


router = APIRouter(prefix="/groups/{group_id}", tags=["ledger"])


@router.post("/expenses", response_model=ExpenseResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    group_id: int, body: ExpenseRequest, user: CurrentUserDep, service: LedgerServiceDep
) -> ExpenseResponse:
    with _ledger_errors():
        return _expense_out(service.create_expense(user, group_id, _to_input(body)))


@router.get("/expenses", response_model=list[ExpenseResponse])
def list_expenses(
    group_id: int, user: CurrentUserDep, service: LedgerServiceDep
) -> list[ExpenseResponse]:
    with _ledger_errors():
        return [_expense_out(expense) for expense in service.list_expenses(user, group_id)]


@router.put("/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    group_id: int,
    expense_id: int,
    body: ExpenseRequest,
    user: CurrentUserDep,
    service: LedgerServiceDep,
) -> ExpenseResponse:
    with _ledger_errors():
        return _expense_out(service.update_expense(user, group_id, expense_id, _to_input(body)))


@router.delete("/expenses/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    group_id: int, expense_id: int, user: CurrentUserDep, service: LedgerServiceDep
) -> None:
    with _ledger_errors():
        service.delete_expense(user, group_id, expense_id)


@router.post("/payments", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def record_payment(
    group_id: int, body: PaymentRequest, user: CurrentUserDep, service: LedgerServiceDep
) -> PaymentResponse:
    with _ledger_errors():
        return _payment_out(
            service.record_payment(user, group_id, body.from_id, body.to_id, body.amount)
        )


@router.get("/payments", response_model=list[PaymentResponse])
def list_payments(
    group_id: int, user: CurrentUserDep, service: LedgerServiceDep
) -> list[PaymentResponse]:
    with _ledger_errors():
        return [_payment_out(payment) for payment in service.list_payments(user, group_id)]


@router.get("/balances", response_model=BalancesResponse)
def balances(group_id: int, user: CurrentUserDep, service: LedgerServiceDep) -> BalancesResponse:
    with _ledger_errors():
        return _balances_out(service.balances(user, group_id))
