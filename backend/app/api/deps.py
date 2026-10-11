from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated, cast

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.repositories.models import User
from app.services.auth import AuthError, AuthService
from app.services.groups import GroupService


@dataclass(frozen=True, slots=True)
class AppContext:
    settings: Settings
    engine: Engine
    session_factory: sessionmaker[Session]


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def get_context(request: Request) -> AppContext:
    return cast(AppContext, request.app.state.context)


ContextDep = Annotated[AppContext, Depends(get_context)]


def get_session(context: ContextDep) -> Iterator[Session]:
    with context.session_factory() as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def get_auth_service(session: SessionDep, context: ContextDep) -> AuthService:
    return AuthService(session, context.settings)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


def get_group_service(session: SessionDep) -> GroupService:
    return GroupService(session)


GroupServiceDep = Annotated[GroupService, Depends(get_group_service)]


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    service: AuthServiceDep,
) -> User:
    if token is None:
        raise unauthorized("not authenticated")
    try:
        return service.user_from_token(token)
    except AuthError:
        raise unauthorized("not authenticated") from None


CurrentUserDep = Annotated[User, Depends(get_current_user)]
