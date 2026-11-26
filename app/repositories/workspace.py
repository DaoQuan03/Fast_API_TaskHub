from typing import Annotated
from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_LIMIT, DEFAULT_PAGE
from app.core.database import get_db
from app.core.exceptions import ConflictException
from app.core.messages import WORKSPACE_MEMBER_ALREADY_EXISTS
from app.models.enums import WorkspaceRole
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Workspace, session)

    async def create_with_owner(
        self,
        *,
        name: str,
        owner_id: int,
    ) -> Workspace:
        workspace = await self.create(name=name, owner_id=owner_id)
        member = WorkspaceMember(
            workspace_id=workspace.id,
            user_id=owner_id,
            role=WorkspaceRole.OWNER,
        )
        self.session.add(member)
        await self.session.flush()
        return workspace

    async def get_multi_for_user(
        self,
        user_id: int,
        *,
        page: int = DEFAULT_PAGE,
        limit: int = DEFAULT_LIMIT,
    ) -> tuple[list[Workspace], int]:
        base_filter = (
            select(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
        )
        count_stmt = (
            select(func.count())
            .select_from(Workspace)
            .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
            .where(WorkspaceMember.user_id == user_id)
        )
        total = await self.session.scalar(count_stmt)
        stmt = (
            base_filter.order_by(Workspace.created_at.asc(), Workspace.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return list(result.all()), total or 0

    async def get_user_by_id(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_member(
        self,
        workspace_id: int,
        user_id: int,
    ) -> WorkspaceMember | None:
        stmt = select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        return await self.session.scalar(stmt)

    async def list_members(
        self,
        workspace_id: int,
    ) -> tuple[list[WorkspaceMember], int]:
        count_stmt = (
            select(func.count())
            .select_from(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
        )
        total = await self.session.scalar(count_stmt)
        stmt = (
            select(WorkspaceMember)
            .where(WorkspaceMember.workspace_id == workspace_id)
            .order_by(WorkspaceMember.user_id.asc())
        )
        result = await self.session.scalars(stmt)
        return list(result.all()), total or 0

    async def add_member(
        self,
        *,
        workspace_id: int,
        user_id: int,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        member = WorkspaceMember(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
        )
        self.session.add(member)
        try:
            await self.session.flush()
            return member
        except IntegrityError:
            await self.session.rollback()
            raise ConflictException(WORKSPACE_MEMBER_ALREADY_EXISTS)

    async def update_member_role(
        self,
        member: WorkspaceMember,
        role: WorkspaceRole,
    ) -> WorkspaceMember:
        member.role = role
        await self.session.flush()
        return member

    async def remove_member(self, member: WorkspaceMember) -> None:
        await self.session.delete(member)
        await self.session.flush()


def get_workspace_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> WorkspaceRepository:
    return WorkspaceRepository(session=session)
