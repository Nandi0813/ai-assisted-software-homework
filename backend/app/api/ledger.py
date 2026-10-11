from collections.abc import Iterator
from contextlib import contextmanager
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException
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
        return ExpenseInput(
            description=body.description,
            amount=body.amount,
            payer_id=body.payer_id,
            split_type=body.split.type,
            participants=list(split.participants),
            shares=[],
        )
    if isinstance(split, ExactSplit):
        return ExpenseInput(
            description=body.description,
            amount=body.amount,
            payer_id=body.payer_id,
            split_type=body.split.type,
            participants=[],
            shares=[ShareInput(s.user_id, s.amount) for s in split.shares],
        )
    return ExpenseInput(
        description=body.description,
        amount=body.amount,
        payer_id=body.payer_id,
        split_type=body.split.type,
        participants=[],
        shares=[ShareInput(s.user_id, s.percent) for s in split.shares],
    )


def _expense_out(e: Expense) -> ExpenseResponse:
    return ExpenseResponse(
        id=e.id,
        description=e.description,
        amount=format_cents(e.amount_cents),
        payer_id=e.payer_id,
        created_by=e.created_by,
        split_type=e.split_type,
        shares=[
            ShareOut(
                user_id=s.user_id,
                amount=format_cents(s.amount_cents),
                percent=format_cents(s.percent_bp) if s.percent_bp is not None else None,
            )
            for s in e.shares
        ],
    )


def _payment_out(p: Payment) -> PaymentResponse:
    return PaymentResponse(
        id=p.id,
        from_id=p.from_id,
        to_id=p.to_id,
        amount=format_cents(p.amount_cents),
        created_by=p.created_by,
    )


def _balances_out(v: BalanceView) -> BalancesResponse:
    names = {m.user_id: m.username for m in v.members}
    return BalancesResponse(
        members=[
            MemberBalanceOut(
                user_id=m.user_id,
                username=m.username,
                balance=format_cents(m.balance_cents),
                active=m.active,
            )
            for m in v.members
        ],
        transfers=[
            TransferOut(
                from_id=t.from_id,
                from_username=names[t.from_id],
                to_id=t.to_id,
                to_username=names[t.to_id],
                amount=format_cents(t.amount_cents),
            )
            for t in v.transfers
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
    except LedgerValidationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from None


router = APIRouter(prefix="/groups/{group_id}", tags=["ledger"])


@router.post("/expenses", status_code=201, response_model=ExpenseResponse)
def create_expense(
    group_id: int,
    body: ExpenseRequest,
    user: CurrentUserDep,
    service: LedgerServiceDep,
) -> ExpenseResponse:
    with _ledger_errors():
        expense = service.create_expense(user, group_id, _to_input(body))
    return _expense_out(expense)


@router.get("/expenses", response_model=list[ExpenseResponse])
def list_expenses(
    group_id: int,
    user: CurrentUserDep,
    service: LedgerServiceDep,
) -> list[ExpenseResponse]:
    with _ledger_errors():
        expenses = service.list_expenses(user, group_id)
    return [_expense_out(e) for e in expenses]


@router.put("/expenses/{expense_id}", response_model=ExpenseResponse)
def update_expense(
    group_id: int,
    expense_id: int,
    body: ExpenseRequest,
    user: CurrentUserDep,
    service: LedgerServiceDep,
) -> ExpenseResponse:
    with _ledger_errors():
        expense = service.update_expense(user, group_id, expense_id, _to_input(body))
    return _expense_out(expense)


@router.delete("/expenses/{expense_id}", status_code=204)
def delete_expense(
    group_id: int,
    expense_id: int,
    user: CurrentUserDep,
    service: LedgerServiceDep,
) -> None:
    with _ledger_errors():
        service.delete_expense(user, group_id, expense_id)


@router.post("/payments", status_code=201, response_model=PaymentResponse)
def record_payment(
    group_id: int,
    body: PaymentRequest,
    user: CurrentUserDep,
    service: LedgerServiceDep,
) -> PaymentResponse:
    with _ledger_errors():
        payment = service.record_payment(user, group_id, body.from_id, body.to_id, body.amount)
    return _payment_out(payment)


@router.get("/payments", response_model=list[PaymentResponse])
def list_payments(
    group_id: int,
    user: CurrentUserDep,
    service: LedgerServiceDep,
) -> list[PaymentResponse]:
    with _ledger_errors():
        payments = service.list_payments(user, group_id)
    return [_payment_out(p) for p in payments]


@router.get("/balances", response_model=BalancesResponse)
def get_balances(
    group_id: int,
    user: CurrentUserDep,
    service: LedgerServiceDep,
) -> BalancesResponse:
    with _ledger_errors():
        view = service.balances(user, group_id)
    return _balances_out(view)
