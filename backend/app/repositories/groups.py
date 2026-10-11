from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.models import Group, GroupMember, User


class GroupRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, name: str) -> Group:
        group = Group(name=name)
        self._session.add(group)
        self._session.flush()
        return group

    def get(self, group_id: int) -> Group | None:
        return self._session.get(Group, group_id)

    def get_membership(self, group_id: int, user_id: int) -> GroupMember | None:
        return self._session.scalars(
            select(GroupMember).where(
                GroupMember.group_id == group_id,
                GroupMember.user_id == user_id,
            )
        ).one_or_none()

    def add_member(self, group_id: int, user_id: int) -> GroupMember:
        member = GroupMember(group_id=group_id, user_id=user_id)
        self._session.add(member)
        self._session.flush()
        return member

    def active_member_users(self, group_id: int) -> list[User]:
        return list(
            self._session.scalars(
                select(User)
                .join(GroupMember, GroupMember.user_id == User.id)
                .where(GroupMember.group_id == group_id, GroupMember.active.is_(True))
                .order_by(GroupMember.id)
            )
        )

    def member_rows(self, group_id: int) -> list[tuple[GroupMember, User]]:
        stmt = (
            select(GroupMember, User)
            .join(User, User.id == GroupMember.user_id)
            .where(GroupMember.group_id == group_id)
            .order_by(GroupMember.id)
        )
        return [(member, user) for member, user in self._session.execute(stmt)]

    def groups_for_user(self, user_id: int) -> list[Group]:
        return list(
            self._session.scalars(
                select(Group)
                .join(GroupMember, GroupMember.group_id == Group.id)
                .where(GroupMember.user_id == user_id, GroupMember.active.is_(True))
                .order_by(Group.id)
            )
        )
