from typing import Annotated

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, StringConstraints

from app.api.deps import CurrentUserDep, GroupServiceDep
from app.services.groups import (
    AlreadyMemberError,
    GroupNotFoundError,
    GroupView,
    UserNotFoundError,
)

GroupName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class CreateGroupRequest(BaseModel):
    name: GroupName


class AddMemberRequest(BaseModel):
    username: str


class MemberResponse(BaseModel):
    id: int
    username: str


class GroupSummaryResponse(BaseModel):
    id: int
    name: str


class GroupDetailResponse(BaseModel):
    id: int
    name: str
    members: list[MemberResponse]


def _detail(view: GroupView) -> GroupDetailResponse:
    return GroupDetailResponse(
        id=view.group.id,
        name=view.group.name,
        members=[MemberResponse(id=u.id, username=u.username) for u in view.members],
    )


def _group_not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="group not found")


router = APIRouter(prefix="/groups", tags=["groups"])


@router.post("", status_code=201, response_model=GroupDetailResponse)
def create_group(
    body: CreateGroupRequest,
    user: CurrentUserDep,
    service: GroupServiceDep,
) -> GroupDetailResponse:
    return _detail(service.create_group(user, body.name))


@router.get("", response_model=list[GroupSummaryResponse])
def list_groups(user: CurrentUserDep, service: GroupServiceDep) -> list[GroupSummaryResponse]:
    return [GroupSummaryResponse(id=g.id, name=g.name) for g in service.list_groups(user)]


@router.get("/{group_id}", response_model=GroupDetailResponse)
def get_group(group_id: int, user: CurrentUserDep, service: GroupServiceDep) -> GroupDetailResponse:
    try:
        view = service.get_group(user, group_id)
    except GroupNotFoundError:
        raise _group_not_found() from None
    return _detail(view)


@router.post("/{group_id}/members", status_code=201, response_model=GroupDetailResponse)
def add_member(
    group_id: int,
    body: AddMemberRequest,
    user: CurrentUserDep,
    service: GroupServiceDep,
) -> GroupDetailResponse:
    try:
        view = service.add_member(user, group_id, body.username)
    except GroupNotFoundError:
        raise _group_not_found() from None
    except UserNotFoundError:
        raise HTTPException(status_code=404, detail="user not found") from None
    except AlreadyMemberError:
        raise HTTPException(status_code=409, detail="user is already a member") from None
    return _detail(view)
