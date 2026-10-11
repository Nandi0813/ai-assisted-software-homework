from datetime import UTC, datetime, timedelta
from typing import Final

import jwt
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.repositories.models import User
from app.repositories.users import UserRepository

_password_hash = PasswordHash.recommended()

JWT_ALGORITHM: Final[str] = "HS256"


class AuthError(Exception):
    pass


class UsernameTakenError(Exception):
    pass


class AuthService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._users = UserRepository(session)

    def register(self, username: str, password: str) -> User:
        try:
            user = self._users.add(username, _password_hash.hash(password))
            self._session.commit()
        except IntegrityError:
            self._session.rollback()
            raise UsernameTakenError(username) from None
        return user

    def authenticate(self, username: str, password: str) -> User:
        user = self._users.get_by_username(username)
        if user is None or not _password_hash.verify(password, user.password_hash):
            raise AuthError("incorrect username or password")
        return user

    def issue_token(self, user: User) -> str:
        expires = datetime.now(UTC) + timedelta(minutes=self._settings.access_token_minutes)
        return jwt.encode(
            {"sub": str(user.id), "exp": expires},
            self._settings.jwt_secret,
            algorithm=JWT_ALGORITHM,
        )

    def user_from_token(self, token: str) -> User:
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[JWT_ALGORITHM],
                options={"require": ["exp", "sub"]},
            )
        except jwt.InvalidTokenError:
            raise AuthError("invalid token") from None
        sub = payload["sub"]
        if not isinstance(sub, str) or not sub.isdigit():
            raise AuthError("invalid token")
        user = self._users.get_by_id(int(sub))
        if user is None:
            raise AuthError("invalid token")
        return user
