from collections.abc import Callable, Coroutine
from datetime import timezone
from typing import Annotated, Any
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import (
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.core.messages import (
    INACTIVE_USER,
    INVALID_OR_EXPIRED_TOKEN,
    PERMISSION_DENIED,
    TASK_NOT_FOUND,
    WORKSPACE_PERMISSION_DENIED,
)
from app.core.security import decode_token
from app.models.enums import TokenType, UserRole, WorkspaceRole
from app.models.task import Task
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.repositories.task import TaskRepository, get_task_repository

http_bearer = HTTPBearer(auto_error=False)

DBSessionDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(http_bearer)],
    session: DBSessionDep,
) -> User:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedException(INVALID_OR_EXPIRED_TOKEN)

    payload = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
    user = await session.get(User, payload["user_id"])
    if not user:
        raise UnauthorizedException(INVALID_OR_EXPIRED_TOKEN)
    if not user.is_active:
        raise UnauthorizedException(INACTIVE_USER)

    if user.password_changed_at is not None:
        pwd_changed = user.password_changed_at
        if pwd_changed.tzinfo is None:
            pwd_changed = pwd_changed.replace(tzinfo=timezone.utc)
        if payload["iat_ts"] < int(pwd_changed.timestamp()):
            raise UnauthorizedException(INVALID_OR_EXPIRED_TOKEN)

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


def require_roles(
    *allowed_roles: UserRole,
) -> Callable[..., Coroutine[Any, Any, User]]:
    async def role_checker(current_user: CurrentUserDep) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(PERMISSION_DENIED)
        return current_user

    return role_checker


AdminUserDep = Annotated[User, Depends(require_roles(UserRole.ADMIN))]


async def verify_task_owner(
    task_id: int,
    current_user: CurrentUserDep,
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> Task:
    task = await repository.get(task_id)
    if not task:
        raise NotFoundException(TASK_NOT_FOUND.format(task_id=task_id))
    if (
        current_user.role != UserRole.ADMIN
        and task.created_by != current_user.id
        and task.assignee_id != current_user.id
    ):
        raise ForbiddenException(PERMISSION_DENIED)
    return task


OwnedTaskDep = Annotated[Task, Depends(verify_task_owner)]


def require_workspace_roles(
    *allowed_roles: WorkspaceRole,
) -> Callable[..., Coroutine[Any, Any, WorkspaceMember]]:
    async def workspace_role_checker(
        workspace_id: int,
        current_user: CurrentUserDep,
        session: DBSessionDep,
    ) -> WorkspaceMember:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == current_user.id,
        )
        member = await session.scalar(stmt)
        if not member or member.role not in allowed_roles:
            raise ForbiddenException(WORKSPACE_PERMISSION_DENIED)
        return member

    return workspace_role_checker
