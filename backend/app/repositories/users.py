from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.models import User


class UserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, user_id: int) -> User | None:
        return self._session.get(User, user_id)

    def get_by_username(self, username: str) -> User | None:
        return self._session.scalars(select(User).where(User.username == username)).one_or_none()

    def add(self, username: str, password_hash: str) -> User:
        user = User(username=username, password_hash=password_hash)
        self._session.add(user)
        self._session.flush()
        return user
