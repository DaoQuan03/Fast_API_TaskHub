from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import timezone
from typing import Annotated, Any
from fastapi import Depends, Path, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import PositiveInt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.constants import (
    DEFAULT_LIMIT,
    DEFAULT_PAGE,
    MAX_LIMIT,
    WORKSPACE_OWNER_ROLES,
    WORKSPACE_READ_ROLES,
    WORKSPACE_WRITE_ROLES,
)
from app.core.database import get_db
from app.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.core.messages import (
    COMMENT_NOT_FOUND,
    INACTIVE_USER,
    INVALID_OR_EXPIRED_TOKEN,
    PERMISSION_DENIED,
    PROJECT_IS_ARCHIVED,
    PROJECT_NOT_FOUND,
    TASK_NOT_FOUND,
    WORKSPACE_NOT_FOUND,
    WORKSPACE_PERMISSION_DENIED,
)
from app.core.security import decode_token
from app.models.comment import Comment
from app.models.enums import ProjectStatus, TokenType, UserRole, WorkspaceRole
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.schemas.base import BaseSchema

http_bearer = HTTPBearer(auto_error=False)

DBSessionDep = Annotated[AsyncSession, Depends(get_db)]

WorkspaceIdPath = Annotated[PositiveInt, Path(description="Workspace ID")]
ProjectIdPath = Annotated[PositiveInt, Path(description="Project ID")]
TaskIdPath = Annotated[PositiveInt, Path(description="Task ID")]
LabelIdPath = Annotated[PositiveInt, Path(description="Label ID")]
CommentIdPath = Annotated[PositiveInt, Path(description="Comment ID")]
UserIdPath = Annotated[PositiveInt, Path(description="User ID")]


class PaginationParams(BaseSchema):
    page: int = DEFAULT_PAGE
    limit: int = DEFAULT_LIMIT

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.limit


def get_pagination_params(
    page: Annotated[int, Query(ge=DEFAULT_PAGE, description="Page number")] = DEFAULT_PAGE,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Items per page")] = DEFAULT_LIMIT,
) -> PaginationParams:
    return PaginationParams(page=page, limit=limit)


PaginationDep = Annotated[PaginationParams, Depends(get_pagination_params)]


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


@dataclass
class WorkspaceAccessContext:
    workspace: Workspace
    role: WorkspaceRole
    current_user: User


@dataclass
class ProjectAccessContext:
    project: Project
    role: WorkspaceRole
    current_user: User


@dataclass
class TaskAccessContext:
    task: Task
    project: Project | None
    role: WorkspaceRole
    current_user: User


@dataclass
class CommentAccessContext:
    comment: Comment
    task: Task
    project: Project | None
    role: WorkspaceRole
    current_user: User


async def resolve_workspace_access(
    workspace_id: int,
    current_user: User,
    session: AsyncSession,
    allowed_roles: frozenset[WorkspaceRole],
) -> WorkspaceAccessContext:
    stmt = (
        select(Workspace, WorkspaceMember.role)
        .outerjoin(
            WorkspaceMember,
            (WorkspaceMember.workspace_id == Workspace.id)
            & (WorkspaceMember.user_id == current_user.id),
        )
        .where(Workspace.id == workspace_id)
    )
    row = (await session.execute(stmt)).first()
    if not row:
        raise NotFoundException(
            WORKSPACE_NOT_FOUND.format(workspace_id=workspace_id)
        )
    workspace, member_role = row
    if current_user.role == UserRole.ADMIN:
        return WorkspaceAccessContext(
            workspace=workspace,
            role=WorkspaceRole.OWNER,
            current_user=current_user,
        )
    if member_role is None or member_role not in allowed_roles:
        raise ForbiddenException(WORKSPACE_PERMISSION_DENIED)
    return WorkspaceAccessContext(
        workspace=workspace,
        role=member_role,
        current_user=current_user,
    )


async def resolve_project_access(
    project_id: int,
    current_user: User,
    session: AsyncSession,
    allowed_roles: frozenset[WorkspaceRole],
    *,
    require_active: bool = False,
) -> ProjectAccessContext:
    stmt = (
        select(Project, WorkspaceMember.role)
        .outerjoin(
            WorkspaceMember,
            (WorkspaceMember.workspace_id == Project.workspace_id)
            & (WorkspaceMember.user_id == current_user.id),
        )
        .where(Project.id == project_id)
    )
    row = (await session.execute(stmt)).first()
    if not row:
        raise NotFoundException(PROJECT_NOT_FOUND.format(project_id=project_id))
    project, member_role = row

    if current_user.role == UserRole.ADMIN:
        effective_role = WorkspaceRole.OWNER
    else:
        if member_role is None or member_role not in allowed_roles:
            raise ForbiddenException(WORKSPACE_PERMISSION_DENIED)
        effective_role = member_role

    if require_active and project.status == ProjectStatus.ARCHIVED:
        raise ConflictException(PROJECT_IS_ARCHIVED)

    return ProjectAccessContext(
        project=project,
        role=effective_role,
        current_user=current_user,
    )


async def resolve_task_access(
    task_id: int,
    current_user: User,
    session: AsyncSession,
    allowed_roles: frozenset[WorkspaceRole],
    *,
    require_active: bool = False,
) -> TaskAccessContext:
    stmt = (
        select(Task, Project, WorkspaceMember.role)
        .options(selectinload(Task.labels))
        .outerjoin(Project, Project.id == Task.project_id)
        .outerjoin(
            WorkspaceMember,
            (WorkspaceMember.workspace_id == Project.workspace_id)
            & (WorkspaceMember.user_id == current_user.id),
        )
        .where(Task.id == task_id)
    )
    row = (await session.execute(stmt)).first()
    if not row:
        raise NotFoundException(TASK_NOT_FOUND.format(task_id=task_id))
    task, project, member_role = row

    if project is not None:
        if current_user.role == UserRole.ADMIN:
            effective_role = WorkspaceRole.OWNER
        else:
            if member_role is None or member_role not in allowed_roles:
                raise ForbiddenException(WORKSPACE_PERMISSION_DENIED)
            effective_role = member_role

        if require_active and project.status == ProjectStatus.ARCHIVED:
            raise ConflictException(PROJECT_IS_ARCHIVED)
    else:
        if current_user.role == UserRole.ADMIN:
            effective_role = WorkspaceRole.OWNER
        else:
            is_owner_or_assignee = (
                task.created_by == current_user.id
                or task.assignee_id == current_user.id
            )
            if not is_owner_or_assignee:
                raise ForbiddenException(PERMISSION_DENIED)
            effective_role = WorkspaceRole.EDITOR

    return TaskAccessContext(
        task=task,
        project=project,
        role=effective_role,
        current_user=current_user,
    )


def require_workspace_roles(
    allowed_roles: frozenset[WorkspaceRole],
) -> Callable[..., Coroutine[Any, Any, WorkspaceAccessContext]]:
    async def workspace_checker(
        workspace_id: WorkspaceIdPath,
        current_user: CurrentUserDep,
        session: DBSessionDep,
    ) -> WorkspaceAccessContext:
        return await resolve_workspace_access(
            workspace_id,
            current_user,
            session,
            allowed_roles,
        )

    return workspace_checker


def require_project_roles(
    allowed_roles: frozenset[WorkspaceRole],
    *,
    require_active: bool = False,
) -> Callable[..., Coroutine[Any, Any, ProjectAccessContext]]:
    async def project_checker(
        project_id: ProjectIdPath,
        current_user: CurrentUserDep,
        session: DBSessionDep,
    ) -> ProjectAccessContext:
        return await resolve_project_access(
            project_id,
            current_user,
            session,
            allowed_roles,
            require_active=require_active,
        )

    return project_checker


def require_task_roles(
    allowed_roles: frozenset[WorkspaceRole],
    *,
    require_active: bool = False,
) -> Callable[..., Coroutine[Any, Any, TaskAccessContext]]:
    async def task_checker(
        task_id: TaskIdPath,
        current_user: CurrentUserDep,
        session: DBSessionDep,
    ) -> TaskAccessContext:
        return await resolve_task_access(
            task_id,
            current_user,
            session,
            allowed_roles,
            require_active=require_active,
        )

    return task_checker


async def verify_comment_modify_access(
    comment_id: CommentIdPath,
    current_user: CurrentUserDep,
    session: DBSessionDep,
) -> CommentAccessContext:
    stmt = (
        select(Comment, Task, Project, WorkspaceMember.role)
        .join(Task, Task.id == Comment.task_id)
        .outerjoin(Project, Project.id == Task.project_id)
        .outerjoin(
            WorkspaceMember,
            (WorkspaceMember.workspace_id == Project.workspace_id)
            & (WorkspaceMember.user_id == current_user.id),
        )
        .where(Comment.id == comment_id)
    )
    row = (await session.execute(stmt)).first()
    if not row:
        raise NotFoundException(COMMENT_NOT_FOUND.format(comment_id=comment_id))
    comment, task, project, member_role = row

    if current_user.role == UserRole.ADMIN:
        effective_role = WorkspaceRole.OWNER
    elif project is not None:
        if member_role is None:
            raise ForbiddenException(WORKSPACE_PERMISSION_DENIED)
        if comment.author_id != current_user.id and member_role != WorkspaceRole.OWNER:
            raise ForbiddenException(PERMISSION_DENIED)
        effective_role = member_role
    else:
        if comment.author_id != current_user.id:
            raise ForbiddenException(PERMISSION_DENIED)
        effective_role = WorkspaceRole.EDITOR

    if project is not None and project.status == ProjectStatus.ARCHIVED:
        raise ConflictException(PROJECT_IS_ARCHIVED)

    return CommentAccessContext(
        comment=comment,
        task=task,
        project=project,
        role=effective_role,
        current_user=current_user,
    )


WorkspaceReadDep = Annotated[
    WorkspaceAccessContext,
    Depends(require_workspace_roles(WORKSPACE_READ_ROLES)),
]
WorkspaceWriteDep = Annotated[
    WorkspaceAccessContext,
    Depends(require_workspace_roles(WORKSPACE_WRITE_ROLES)),
]
WorkspaceOwnerDep = Annotated[
    WorkspaceAccessContext,
    Depends(require_workspace_roles(WORKSPACE_OWNER_ROLES)),
]

ProjectReadDep = Annotated[
    ProjectAccessContext,
    Depends(require_project_roles(WORKSPACE_READ_ROLES, require_active=False)),
]
ProjectWriteActiveDep = Annotated[
    ProjectAccessContext,
    Depends(require_project_roles(WORKSPACE_WRITE_ROLES, require_active=True)),
]
ProjectWriteAnyStatusDep = Annotated[
    ProjectAccessContext,
    Depends(require_project_roles(WORKSPACE_WRITE_ROLES, require_active=False)),
]

TaskReadDep = Annotated[
    TaskAccessContext,
    Depends(require_task_roles(WORKSPACE_READ_ROLES, require_active=False)),
]
TaskWriteActiveDep = Annotated[
    TaskAccessContext,
    Depends(require_task_roles(WORKSPACE_WRITE_ROLES, require_active=True)),
]

CommentModifyDep = Annotated[
    CommentAccessContext,
    Depends(verify_comment_modify_access),
]
