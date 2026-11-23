from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.exceptions import ForbiddenException, UnauthorizedException
from app.core.messages import (
    INACTIVE_USER,
    INVALID_OR_EXPIRED_TOKEN,
    PERMISSION_DENIED,
    WORKSPACE_PERMISSION_DENIED,
)
from app.core.security import decode_token
from app.models.enums import TokenType, UserRole, WorkspaceRole
from app.models.user import User
from app.models.workspace import WorkspaceMember

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

DBSessionDep = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: DBSessionDep,
) -> User:
    payload = decode_token(token, expected_type=TokenType.ACCESS)
    user = await session.get(User, payload["user_id"])
    if not user:
        raise UnauthorizedException(INVALID_OR_EXPIRED_TOKEN)
    if not user.is_active:
        raise UnauthorizedException(INACTIVE_USER)
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
