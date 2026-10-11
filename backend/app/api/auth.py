import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import AfterValidator, BaseModel, StringConstraints

from app.api.deps import AuthServiceDep, CurrentUserDep, unauthorized
from app.services.auth import AuthError, UsernameTakenError

_USERNAME_RE = re.compile(r"[a-z0-9_]{3,32}")


def _normalize_username(value: str) -> str:
    lowered = value.lower()
    if _USERNAME_RE.fullmatch(lowered) is None:
        raise ValueError("username must be 3-32 characters of letters, digits or underscore")
    return lowered


Username = Annotated[str, AfterValidator(_normalize_username)]
Password = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class RegisterRequest(BaseModel):
    username: Username
    password: Password


class UserResponse(BaseModel):
    id: int
    username: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"]


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201, response_model=UserResponse)
def register(body: RegisterRequest, service: AuthServiceDep) -> UserResponse:
    try:
        user = service.register(body.username, body.password)
    except UsernameTakenError:
        raise HTTPException(status_code=409, detail="username already taken") from None
    return UserResponse(id=user.id, username=user.username)


@router.post("/login", response_model=TokenResponse)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: AuthServiceDep,
) -> TokenResponse:
    try:
        user = service.authenticate(form.username.lower(), form.password)
    except AuthError:
        raise unauthorized("incorrect username or password") from None
    return TokenResponse(access_token=service.issue_token(user), token_type="bearer")


@router.get("/me", response_model=UserResponse)
def me(user: CurrentUserDep) -> UserResponse:
    return UserResponse(id=user.id, username=user.username)
