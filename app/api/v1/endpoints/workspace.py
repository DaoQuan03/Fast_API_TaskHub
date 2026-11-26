from typing import Annotated
from fastapi import APIRouter, Depends, Query, status

from app.core.constants import DEFAULT_LIMIT, DEFAULT_PAGE, MAX_LIMIT
from app.dependencies import (
    CurrentUserDep,
    WorkspaceMemberViewDep,
    WorkspaceOwnerDep,
)
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
from app.services.workspace import WorkspaceService, get_workspace_service

router = APIRouter()

WorkspaceServiceDep = Annotated[WorkspaceService, Depends(get_workspace_service)]

AUTH_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
}
WORKSPACE_ACCESS_RESPONSES = {
    **AUTH_RESPONSES,
    status.HTTP_403_FORBIDDEN: {"description": "Insufficient permissions in workspace"},
    status.HTTP_404_NOT_FOUND: {"description": "Workspace not found"},
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
    service: WorkspaceServiceDep,
    page: Annotated[int, Query(ge=DEFAULT_PAGE, description="Page number")] = DEFAULT_PAGE,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Items per page")] = DEFAULT_LIMIT,
) -> WorkspaceListResponse:
    return await service.list_workspaces(current_user, page=page, limit=limit)


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
    workspace_id: int,
    _member: WorkspaceMemberViewDep,
    service: WorkspaceServiceDep,
) -> WorkspaceResponse:
    return await service.get_workspace(workspace_id)


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
    workspace_id: int,
    data: WorkspaceUpdate,
    _owner: WorkspaceOwnerDep,
    service: WorkspaceServiceDep,
) -> WorkspaceResponse:
    return await service.update_workspace(workspace_id, data)


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
    workspace_id: int,
    _owner: WorkspaceOwnerDep,
    service: WorkspaceServiceDep,
) -> None:
    await service.delete_workspace(workspace_id)


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
    workspace_id: int,
    _member: WorkspaceMemberViewDep,
    service: WorkspaceServiceDep,
) -> WorkspaceMemberListResponse:
    return await service.list_members(workspace_id)


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
    workspace_id: int,
    data: WorkspaceMemberCreate,
    _owner: WorkspaceOwnerDep,
    service: WorkspaceServiceDep,
) -> WorkspaceMemberResponse:
    return await service.add_member(workspace_id, data)


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
    workspace_id: int,
    user_id: int,
    data: WorkspaceMemberUpdate,
    _owner: WorkspaceOwnerDep,
    service: WorkspaceServiceDep,
) -> WorkspaceMemberResponse:
    return await service.update_member_role(workspace_id, user_id, data)


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
    workspace_id: int,
    user_id: int,
    _owner: WorkspaceOwnerDep,
    service: WorkspaceServiceDep,
) -> None:
    await service.remove_member(workspace_id, user_id)
