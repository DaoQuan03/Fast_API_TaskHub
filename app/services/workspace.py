from typing import Annotated
from fastapi import Depends

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.messages import (
    CANNOT_REMOVE_OR_DEMOTE_WORKSPACE_OWNER,
    LABEL_NOT_FOUND,
    USER_NOT_FOUND,
    WORKSPACE_MEMBER_NOT_FOUND,
)
from app.dependencies import (
    PaginationParams,
    ProjectAccessContext,
    WorkspaceAccessContext,
)
from app.models.enums import ProjectStatus, WorkspaceRole
from app.models.user import User
from app.repositories.workspace import WorkspaceRepository, get_workspace_repository
from app.schemas.workspace import (
    LabelCreate,
    LabelListResponse,
    LabelResponse,
    LabelUpdate,
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
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
        pagination: PaginationParams,
    ) -> WorkspaceListResponse:
        items, total = await self.repository.get_multi_for_user(
            current_user.id,
            pagination=pagination,
        )
        return WorkspaceListResponse(
            items=[WorkspaceResponse.model_validate(item) for item in items],
            total=total,
        )

    async def get_workspace(
        self,
        access: WorkspaceAccessContext,
    ) -> WorkspaceResponse:
        return WorkspaceResponse.model_validate(access.workspace)

    async def update_workspace(
        self,
        access: WorkspaceAccessContext,
        data: WorkspaceUpdate,
    ) -> WorkspaceResponse:
        update_data = data.model_dump(exclude_unset=True)
        updated = await self.repository.update(access.workspace, update_data)
        return WorkspaceResponse.model_validate(updated)

    async def delete_workspace(
        self,
        access: WorkspaceAccessContext,
    ) -> None:
        await self.repository.delete(access.workspace)

    async def list_members(
        self,
        access: WorkspaceAccessContext,
        pagination: PaginationParams,
    ) -> WorkspaceMemberListResponse:
        items, total = await self.repository.list_members(
            access.workspace.id,
            pagination=pagination,
        )
        return WorkspaceMemberListResponse(
            items=[WorkspaceMemberResponse.model_validate(item) for item in items],
            total=total,
        )

    async def add_member(
        self,
        access: WorkspaceAccessContext,
        data: WorkspaceMemberCreate,
    ) -> WorkspaceMemberResponse:
        target_user = await self.repository.get_user_by_id(data.user_id)
        if not target_user:
            raise NotFoundException(USER_NOT_FOUND.format(user_id=data.user_id))

        member = await self.repository.add_member(
            workspace_id=access.workspace.id,
            user_id=data.user_id,
            role=data.role,
        )
        return WorkspaceMemberResponse.model_validate(member)

    async def update_member_role(
        self,
        access: WorkspaceAccessContext,
        target_user_id: int,
        data: WorkspaceMemberUpdate,
    ) -> WorkspaceMemberResponse:
        workspace = access.workspace
        if workspace.owner_id == target_user_id and data.role != WorkspaceRole.OWNER:
            raise BadRequestException(CANNOT_REMOVE_OR_DEMOTE_WORKSPACE_OWNER)

        member = await self.repository.get_member(workspace.id, target_user_id)
        if not member:
            raise NotFoundException(
                WORKSPACE_MEMBER_NOT_FOUND.format(
                    user_id=target_user_id,
                    workspace_id=workspace.id,
                )
            )

        updated = await self.repository.update_member_role(member, data.role)
        return WorkspaceMemberResponse.model_validate(updated)

    async def remove_member(
        self,
        access: WorkspaceAccessContext,
        target_user_id: int,
    ) -> None:
        workspace = access.workspace
        if workspace.owner_id == target_user_id:
            raise BadRequestException(CANNOT_REMOVE_OR_DEMOTE_WORKSPACE_OWNER)

        member = await self.repository.get_member(workspace.id, target_user_id)
        if not member:
            raise NotFoundException(
                WORKSPACE_MEMBER_NOT_FOUND.format(
                    user_id=target_user_id,
                    workspace_id=workspace.id,
                )
            )

        await self.repository.remove_member(member)

    async def create_project(
        self,
        access: WorkspaceAccessContext,
        data: ProjectCreate,
    ) -> ProjectResponse:
        project = await self.repository.create_project(
            workspace_id=access.workspace.id,
            name=data.name,
            description=data.description,
        )
        return ProjectResponse.model_validate(project)

    async def list_projects(
        self,
        access: WorkspaceAccessContext,
        pagination: PaginationParams,
    ) -> ProjectListResponse:
        items, total = await self.repository.list_projects(
            access.workspace.id,
            pagination=pagination,
        )
        return ProjectListResponse(
            items=[ProjectResponse.model_validate(item) for item in items],
            total=total,
        )

    async def get_project(
        self,
        access: ProjectAccessContext,
    ) -> ProjectResponse:
        return ProjectResponse.model_validate(access.project)

    async def update_project(
        self,
        access: ProjectAccessContext,
        data: ProjectUpdate,
    ) -> ProjectResponse:
        update_data = data.model_dump(exclude_unset=True)
        updated = await self.repository.update_project(access.project, update_data)
        return ProjectResponse.model_validate(updated)

    async def set_project_status(
        self,
        access: ProjectAccessContext,
        status: ProjectStatus,
    ) -> ProjectResponse:
        updated = await self.repository.update_project(
            access.project,
            {"status": status},
        )
        return ProjectResponse.model_validate(updated)

    async def delete_project(
        self,
        access: ProjectAccessContext,
    ) -> None:
        await self.repository.delete_project(access.project)

    async def create_label(
        self,
        access: ProjectAccessContext,
        data: LabelCreate,
    ) -> LabelResponse:
        label = await self.repository.create_label(
            project_id=access.project.id,
            name=data.name,
            color=data.color,
        )
        return LabelResponse.model_validate(label)

    async def list_labels(
        self,
        access: ProjectAccessContext,
        pagination: PaginationParams,
    ) -> LabelListResponse:
        items, total = await self.repository.list_labels(
            access.project.id,
            pagination=pagination,
        )
        return LabelListResponse(
            items=[LabelResponse.model_validate(item) for item in items],
            total=total,
        )

    async def update_label(
        self,
        access: ProjectAccessContext,
        label_id: int,
        data: LabelUpdate,
    ) -> LabelResponse:
        label = await self.repository.get_label_in_project(
            access.project.id,
            label_id,
        )
        if not label:
            raise NotFoundException(LABEL_NOT_FOUND.format(label_id=label_id))
        update_data = data.model_dump(exclude_unset=True)
        updated = await self.repository.update_label(label, update_data)
        return LabelResponse.model_validate(updated)

    async def delete_label(
        self,
        access: ProjectAccessContext,
        label_id: int,
    ) -> None:
        label = await self.repository.get_label_in_project(
            access.project.id,
            label_id,
        )
        if not label:
            raise NotFoundException(LABEL_NOT_FOUND.format(label_id=label_id))
        await self.repository.delete_label(label)


def get_workspace_service(
    repository: Annotated[WorkspaceRepository, Depends(get_workspace_repository)],
) -> WorkspaceService:
    return WorkspaceService(repository=repository)
