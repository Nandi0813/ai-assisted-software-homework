from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.repositories.groups import GroupRepository
from app.repositories.models import Group, User
from app.repositories.users import UserRepository


class GroupNotFoundError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class AlreadyMemberError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class GroupView:
    group: Group
    members: list[User]
    former_members: list[User]


def require_active_member(groups: GroupRepository, user: User, group_id: int) -> Group:
    group = groups.get(group_id)
    if group is None:
        raise GroupNotFoundError(group_id)
    membership = groups.get_membership(group_id, user.id)
    if membership is None or not membership.active:
        raise GroupNotFoundError(group_id)
    return group


class GroupService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._groups = GroupRepository(session)
        self._users = UserRepository(session)

    def _view(self, group: Group) -> GroupView:
        rows = self._groups.member_rows(group.id)
        members = [u for m, u in rows if m.active]
        former_members = [u for m, u in rows if not m.active]
        return GroupView(group=group, members=members, former_members=former_members)

    def create_group(self, owner: User, name: str) -> GroupView:
        group = self._groups.create(name)
        self._groups.add_member(group.id, owner.id)
        self._session.commit()
        return self._view(group)

    def list_groups(self, user: User) -> list[Group]:
        return self._groups.groups_for_user(user.id)

    def get_group(self, user: User, group_id: int) -> GroupView:
        return self._view(require_active_member(self._groups, user, group_id))

    def add_member(self, actor: User, group_id: int, username: str) -> GroupView:
        group = require_active_member(self._groups, actor, group_id)
        target = self._users.get_by_username(username.lower())
        if target is None:
            raise UserNotFoundError(username)
        membership = self._groups.get_membership(group_id, target.id)
        if membership is not None and membership.active:
            raise AlreadyMemberError(username)
        if membership is not None:
            membership.active = True
        else:
            self._groups.add_member(group_id, target.id)
        self._session.commit()
        return self._view(group)
