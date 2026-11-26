from typing import Annotated
from fastapi import Depends

from app.core.constants import DEFAULT_LIMIT, DEFAULT_PAGE
from app.core.exceptions import BadRequestException, NotFoundException
from app.core.messages import (
    CANNOT_REMOVE_OR_DEMOTE_WORKSPACE_OWNER,
    USER_NOT_FOUND,
    WORKSPACE_MEMBER_NOT_FOUND,
    WORKSPACE_NOT_FOUND,
)
from app.models.enums import WorkspaceRole
from app.models.user import User
from app.repositories.workspace import WorkspaceRepository, get_workspace_repository
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceListResponse,
    WorkspaceMemberCreate,
    WorkspaceMemberListResponse,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdate,
    WorkspaceResponse,
    WorkspaceUpdate,
)


class WorkspaceService:
    def __init__(self, repository: WorkspaceRepository) -> None:
        self.repository = repository

    async def create_workspace(
        self,
        data: WorkspaceCreate,
        current_user: User,
    ) -> WorkspaceResponse:
        workspace = await self.repository.create_with_owner(
            name=data.name,
            owner_id=current_user.id,
        )
        return WorkspaceResponse.model_validate(workspace)

    async def list_workspaces(
        self,
        current_user: User,
        *,
        page: int = DEFAULT_PAGE,
        limit: int = DEFAULT_LIMIT,
    ) -> WorkspaceListResponse:
        items, total = await self.repository.get_multi_for_user(
            current_user.id,
            page=page,
            limit=limit,
        )
        return WorkspaceListResponse(
            items=[WorkspaceResponse.model_validate(item) for item in items],
            total=total,
        )

    async def get_workspace(self, workspace_id: int) -> WorkspaceResponse:
        workspace = await self.repository.get(workspace_id)
        if not workspace:
            raise NotFoundException(
                WORKSPACE_NOT_FOUND.format(workspace_id=workspace_id)
            )
        return WorkspaceResponse.model_validate(workspace)

    async def update_workspace(
        self,
        workspace_id: int,
        data: WorkspaceUpdate,
    ) -> WorkspaceResponse:
        workspace = await self.repository.get(workspace_id)
        if not workspace:
            raise NotFoundException(
                WORKSPACE_NOT_FOUND.format(workspace_id=workspace_id)
            )
        update_data = data.model_dump(exclude_unset=True)
        updated = await self.repository.update(workspace, update_data)
        return WorkspaceResponse.model_validate(updated)

    async def delete_workspace(self, workspace_id: int) -> None:
        workspace = await self.repository.get(workspace_id)
        if not workspace:
            raise NotFoundException(
                WORKSPACE_NOT_FOUND.format(workspace_id=workspace_id)
            )
        await self.repository.delete(workspace)

    async def list_members(self, workspace_id: int) -> WorkspaceMemberListResponse:
        items, total = await self.repository.list_members(workspace_id)
        return WorkspaceMemberListResponse(
            items=[WorkspaceMemberResponse.model_validate(item) for item in items],
            total=total,
        )

    async def add_member(
        self,
        workspace_id: int,
        data: WorkspaceMemberCreate,
    ) -> WorkspaceMemberResponse:
        target_user = await self.repository.get_user_by_id(data.user_id)
        if not target_user:
            raise NotFoundException(USER_NOT_FOUND.format(user_id=data.user_id))

        member = await self.repository.add_member(
            workspace_id=workspace_id,
            user_id=data.user_id,
            role=data.role,
        )
        return WorkspaceMemberResponse.model_validate(member)

    async def update_member_role(
        self,
        workspace_id: int,
        target_user_id: int,
        data: WorkspaceMemberUpdate,
    ) -> WorkspaceMemberResponse:
        workspace = await self.repository.get(workspace_id)
        if not workspace:
            raise NotFoundException(
                WORKSPACE_NOT_FOUND.format(workspace_id=workspace_id)
            )
        if workspace.owner_id == target_user_id and data.role != WorkspaceRole.OWNER:
            raise BadRequestException(CANNOT_REMOVE_OR_DEMOTE_WORKSPACE_OWNER)

        member = await self.repository.get_member(workspace_id, target_user_id)
        if not member:
            raise NotFoundException(
                WORKSPACE_MEMBER_NOT_FOUND.format(
                    user_id=target_user_id,
                    workspace_id=workspace_id,
                )
            )

        updated = await self.repository.update_member_role(member, data.role)
        return WorkspaceMemberResponse.model_validate(updated)

    async def remove_member(
        self,
        workspace_id: int,
        target_user_id: int,
    ) -> None:
        workspace = await self.repository.get(workspace_id)
        if not workspace:
            raise NotFoundException(
                WORKSPACE_NOT_FOUND.format(workspace_id=workspace_id)
            )
        if workspace.owner_id == target_user_id:
            raise BadRequestException(CANNOT_REMOVE_OR_DEMOTE_WORKSPACE_OWNER)

        member = await self.repository.get_member(workspace_id, target_user_id)
        if not member:
            raise NotFoundException(
                WORKSPACE_MEMBER_NOT_FOUND.format(
                    user_id=target_user_id,
                    workspace_id=workspace_id,
                )
            )

        await self.repository.remove_member(member)


def get_workspace_service(
    repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> WorkspaceService:
    return WorkspaceService(repository=repository)
