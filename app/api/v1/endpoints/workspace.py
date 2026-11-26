from typing import Annotated
from fastapi import APIRouter, Depends, status

from app.dependencies import (
    CurrentUserDep,
    LabelIdPath,
    PaginationDep,
    ProjectReadDep,
    ProjectWriteActiveDep,
    ProjectWriteAnyStatusDep,
    UserIdPath,
    WorkspaceOwnerDep,
    WorkspaceReadDep,
    WorkspaceWriteDep,
)
from app.models.enums import ProjectStatus
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
from app.services.workspace import WorkspaceService, get_workspace_service

router = APIRouter()
projects_router = APIRouter()

WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]

AUTH_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
}
WORKSPACE_ACCESS_RESPONSES = {
    **AUTH_RESPONSES,
    status.HTTP_403_FORBIDDEN: {"description": "Insufficient permissions in workspace"},
    status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
}
PROJECT_WRITE_RESPONSES = {
    **WORKSPACE_ACCESS_RESPONSES,
    status.HTTP_409_CONFLICT: {"description": "Project is archived or conflict"},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
}


@router.post(
    "",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new workspace",
    responses={
        status.HTTP_201_CREATED: {"description": "Workspace created successfully"},
        **AUTH_RESPONSES,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
    },
)
async def create_workspace(
    data: WorkspaceCreate,
    current_user: CurrentUserDep,
    service: WorkspaceServiceDep,
) -> WorkspaceResponse:
    return await service.create_workspace(data, current_user)


@router.get(
    "",
    response_model=WorkspaceListResponse,
    summary="List workspaces current user belongs to",
    responses={
        status.HTTP_200_OK: {"description": "Workspaces retrieved successfully"},
        **AUTH_RESPONSES,
    },
)
async def list_workspaces(
    current_user: CurrentUserDep,
    pagination: PaginationDep,
    service: WorkspaceServiceDep,
) -> WorkspaceListResponse:
    return await service.list_workspaces(current_user, pagination=pagination)


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Get workspace details by ID",
    responses={
        status.HTTP_200_OK: {"description": "Workspace retrieved successfully"},
        **WORKSPACE_ACCESS_RESPONSES,
    },
)
async def get_workspace(
    access: WorkspaceReadDep,
    service: WorkspaceServiceDep,
) -> WorkspaceResponse:
    return await service.get_workspace(access)


@router.patch(
    "/{workspace_id}",
    response_model=WorkspaceResponse,
    summary="Update workspace by ID (Owner only)",
    responses={
        status.HTTP_200_OK: {"description": "Workspace updated successfully"},
        **WORKSPACE_ACCESS_RESPONSES,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
    },
)
async def update_workspace(
    data: WorkspaceUpdate,
    access: WorkspaceOwnerDep,
    service: WorkspaceServiceDep,
) -> WorkspaceResponse:
    return await service.update_workspace(access, data)


@router.delete(
    "/{workspace_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete workspace by ID (Owner only)",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Workspace deleted successfully"},
        **WORKSPACE_ACCESS_RESPONSES,
    },
)
async def delete_workspace(
    access: WorkspaceOwnerDep,
    service: WorkspaceServiceDep,
) -> None:
    await service.delete_workspace(access)


@router.get(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberListResponse,
    summary="List all members of a workspace",
    responses={
        status.HTTP_200_OK: {"description": "Members retrieved successfully"},
        **WORKSPACE_ACCESS_RESPONSES,
    },
)
async def list_workspace_members(
    access: WorkspaceReadDep,
    pagination: PaginationDep,
    service: WorkspaceServiceDep,
) -> WorkspaceMemberListResponse:
    return await service.list_members(access, pagination=pagination)


@router.post(
    "/{workspace_id}/members",
    response_model=WorkspaceMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member to a workspace (Owner only)",
    responses={
        status.HTTP_201_CREATED: {"description": "Member added successfully"},
        **WORKSPACE_ACCESS_RESPONSES,
        status.HTTP_409_CONFLICT: {"description": "User is already a member"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
    },
)
async def add_workspace_member(
    data: WorkspaceMemberCreate,
    access: WorkspaceOwnerDep,
    service: WorkspaceServiceDep,
) -> WorkspaceMemberResponse:
    return await service.add_member(access, data)


@router.patch(
    "/{workspace_id}/members/{user_id}",
    response_model=WorkspaceMemberResponse,
    summary="Update a member's role in workspace (Owner only)",
    responses={
        status.HTTP_200_OK: {"description": "Member role updated successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Cannot demote workspace owner"},
        **WORKSPACE_ACCESS_RESPONSES,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
    },
)
async def update_workspace_member(
    user_id: UserIdPath,
    data: WorkspaceMemberUpdate,
    access: WorkspaceOwnerDep,
    service: WorkspaceServiceDep,
) -> WorkspaceMemberResponse:
    return await service.update_member_role(access, user_id, data)


@router.delete(
    "/{workspace_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from workspace (Owner only)",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Member removed successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Cannot remove workspace owner"},
        **WORKSPACE_ACCESS_RESPONSES,
    },
)
async def remove_workspace_member(
    user_id: UserIdPath,
    access: WorkspaceOwnerDep,
    service: WorkspaceServiceDep,
) -> None:
    await service.remove_member(access, user_id)


@router.post(
    "/{workspace_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new project in workspace",
    responses={
        status.HTTP_201_CREATED: {"description": "Project created successfully"},
        **WORKSPACE_ACCESS_RESPONSES,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
    },
)
async def create_project(
    data: ProjectCreate,
    access: WorkspaceWriteDep,
    service: WorkspaceServiceDep,
) -> ProjectResponse:
    return await service.create_project(access, data)


@router.get(
    "/{workspace_id}/projects",
    response_model=ProjectListResponse,
    summary="List projects in workspace",
    responses={
        status.HTTP_200_OK: {"description": "Projects retrieved successfully"},
        **WORKSPACE_ACCESS_RESPONSES,
    },
)
async def list_projects(
    access: WorkspaceReadDep,
    pagination: PaginationDep,
    service: WorkspaceServiceDep,
) -> ProjectListResponse:
    return await service.list_projects(access, pagination=pagination)


@projects_router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Get project details by ID",
    responses={
        status.HTTP_200_OK: {"description": "Project retrieved successfully"},
        **WORKSPACE_ACCESS_RESPONSES,
    },
)
async def get_project(
    access: ProjectReadDep,
    service: WorkspaceServiceDep,
) -> ProjectResponse:
    return await service.get_project(access)


@projects_router.patch(
    "/{project_id}",
    response_model=ProjectResponse,
    summary="Update project details",
    responses={
        status.HTTP_200_OK: {"description": "Project updated successfully"},
        **PROJECT_WRITE_RESPONSES,
    },
)
async def update_project(
    data: ProjectUpdate,
    access: ProjectWriteActiveDep,
    service: WorkspaceServiceDep,
) -> ProjectResponse:
    return await service.update_project(access, data)


@projects_router.post(
    "/{project_id}/archive",
    response_model=ProjectResponse,
    summary="Archive a project",
    responses={
        status.HTTP_200_OK: {"description": "Project archived successfully"},
        **WORKSPACE_ACCESS_RESPONSES,
    },
)
async def archive_project(
    access: ProjectWriteAnyStatusDep,
    service: WorkspaceServiceDep,
) -> ProjectResponse:
    return await service.set_project_status(access, ProjectStatus.ARCHIVED)


@projects_router.post(
    "/{project_id}/unarchive",
    response_model=ProjectResponse,
    summary="Unarchive a project",
    responses={
        status.HTTP_200_OK: {"description": "Project unarchived successfully"},
        **WORKSPACE_ACCESS_RESPONSES,
    },
)
async def unarchive_project(
    access: ProjectWriteAnyStatusDep,
    service: WorkspaceServiceDep,
) -> ProjectResponse:
    return await service.set_project_status(access, ProjectStatus.ACTIVE)


@projects_router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a project",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Project deleted successfully"},
        **WORKSPACE_ACCESS_RESPONSES,
    },
)
async def delete_project(
    access: ProjectWriteAnyStatusDep,
    service: WorkspaceServiceDep,
) -> None:
    await service.delete_project(access)


@projects_router.post(
    "/{project_id}/labels",
    response_model=LabelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a label in project",
    responses={
        status.HTTP_201_CREATED: {"description": "Label created successfully"},
        **PROJECT_WRITE_RESPONSES,
    },
)
async def create_label(
    data: LabelCreate,
    access: ProjectWriteActiveDep,
    service: WorkspaceServiceDep,
) -> LabelResponse:
    return await service.create_label(access, data)


@projects_router.get(
    "/{project_id}/labels",
    response_model=LabelListResponse,
    summary="List labels in project",
    responses={
        status.HTTP_200_OK: {"description": "Labels retrieved successfully"},
        **WORKSPACE_ACCESS_RESPONSES,
    },
)
async def list_labels(
    access: ProjectReadDep,
    pagination: PaginationDep,
    service: WorkspaceServiceDep,
) -> LabelListResponse:
    return await service.list_labels(access, pagination=pagination)


@projects_router.patch(
    "/{project_id}/labels/{label_id}",
    response_model=LabelResponse,
    summary="Update a label in project",
    responses={
        status.HTTP_200_OK: {"description": "Label updated successfully"},
        **PROJECT_WRITE_RESPONSES,
    },
)
async def update_label(
    label_id: LabelIdPath,
    data: LabelUpdate,
    access: ProjectWriteActiveDep,
    service: WorkspaceServiceDep,
) -> LabelResponse:
    return await service.update_label(access, label_id, data)


@projects_router.delete(
    "/{project_id}/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a label in project",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Label deleted successfully"},
        **PROJECT_WRITE_RESPONSES,
    },
)
async def delete_label(
    label_id: LabelIdPath,
    access: ProjectWriteActiveDep,
    service: WorkspaceServiceDep,
) -> None:
    await service.delete_label(access, label_id)
