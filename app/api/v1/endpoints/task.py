from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from pydantic import PositiveInt

from app.dependencies import (
    CommentModifyDep,
    CurrentUserDep,
    LabelIdPath,
    PaginationDep,
    TaskReadDep,
    TaskWriteActiveDep,
)
from app.models.enums import TaskPriority, TaskStatus
from app.schemas.task import (
    CommentCreate,
    CommentListResponse,
    CommentResponse,
    CommentUpdate,
    TaskCreate,
    TaskFilterParams,
    TaskListResponse,
    TaskResponse,
    TaskUpdate,
)
from app.services.task import TaskService, get_task_service

router = APIRouter()
comments_router = APIRouter()

TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]

AUTH_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
}
NOT_FOUND_RESPONSE = {
    status.HTTP_404_NOT_FOUND: {"description": "Resource not found"},
}
FORBIDDEN_RESPONSE = {
    status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
}
TASK_WRITE_RESPONSES = {
    **AUTH_RESPONSES,
    **FORBIDDEN_RESPONSE,
    **NOT_FOUND_RESPONSE,
    status.HTTP_409_CONFLICT: {"description": "Project is archived or conflict"},
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
}


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
    responses={
        status.HTTP_201_CREATED: {"description": "Task created successfully"},
        **TASK_WRITE_RESPONSES,
    },
)
async def create_task(
    data: TaskCreate,
    service: TaskServiceDep,
    current_user: CurrentUserDep,
) -> TaskResponse:
    return await service.create_task(data, current_user=current_user)


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List all tasks with filtering and pagination",
    responses={
        status.HTTP_200_OK: {"description": "List of tasks retrieved successfully"},
        **AUTH_RESPONSES,
        **FORBIDDEN_RESPONSE,
    },
)
async def list_tasks(
    service: TaskServiceDep,
    current_user: CurrentUserDep,
    pagination: PaginationDep,
    status_filter: Annotated[
        list[TaskStatus] | None,
        Query(alias="status", description="Filter by task statuses"),
    ] = None,
    priority_filter: Annotated[
        list[TaskPriority] | None,
        Query(alias="priority", description="Filter by task priorities"),
    ] = None,
    assignee_id: Annotated[
        PositiveInt | None,
        Query(description="Filter by assignee user ID"),
    ] = None,
    project_id: Annotated[
        PositiveInt | None,
        Query(description="Filter by project ID"),
    ] = None,
) -> TaskListResponse:
    filters = TaskFilterParams(
        status=status_filter,
        priority=priority_filter,
        assignee_id=assignee_id,
        project_id=project_id,
    )
    return await service.list_tasks(
        current_user=current_user,
        pagination=pagination,
        filters=filters,
    )


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get a task by ID",
    responses={
        status.HTTP_200_OK: {"description": "Task retrieved successfully"},
        **AUTH_RESPONSES,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
    },
)
async def get_task(
    access: TaskReadDep,
    service: TaskServiceDep,
) -> TaskResponse:
    return await service.get_task(access)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update a task by ID",
    responses={
        status.HTTP_200_OK: {"description": "Task updated successfully"},
        **TASK_WRITE_RESPONSES,
    },
)
async def update_task(
    data: TaskUpdate,
    access: TaskWriteActiveDep,
    service: TaskServiceDep,
) -> TaskResponse:
    return await service.update_task(access, data)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task by ID",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Task deleted successfully"},
        **TASK_WRITE_RESPONSES,
    },
)
async def delete_task(
    access: TaskWriteActiveDep,
    service: TaskServiceDep,
) -> None:
    await service.delete_task(access)


@router.post(
    "/{task_id}/labels/{label_id}",
    response_model=TaskResponse,
    summary="Attach a label to a task",
    responses={
        status.HTTP_200_OK: {"description": "Label attached successfully"},
        **TASK_WRITE_RESPONSES,
    },
)
async def attach_label_to_task(
    label_id: LabelIdPath,
    access: TaskWriteActiveDep,
    service: TaskServiceDep,
) -> TaskResponse:
    return await service.attach_label(access, label_id)


@router.delete(
    "/{task_id}/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Detach a label from a task",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Label detached successfully"},
        **TASK_WRITE_RESPONSES,
    },
)
async def detach_label_from_task(
    label_id: LabelIdPath,
    access: TaskWriteActiveDep,
    service: TaskServiceDep,
) -> None:
    await service.detach_label(access, label_id)


@router.post(
    "/{task_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a comment to a task",
    responses={
        status.HTTP_201_CREATED: {"description": "Comment created successfully"},
        **TASK_WRITE_RESPONSES,
    },
)
async def create_comment(
    data: CommentCreate,
    access: TaskWriteActiveDep,
    service: TaskServiceDep,
) -> CommentResponse:
    return await service.create_comment(access, data)


@router.get(
    "/{task_id}/comments",
    response_model=CommentListResponse,
    summary="List comments of a task",
    responses={
        status.HTTP_200_OK: {"description": "Comments retrieved successfully"},
        **AUTH_RESPONSES,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
    },
)
async def list_comments(
    access: TaskReadDep,
    pagination: PaginationDep,
    service: TaskServiceDep,
) -> CommentListResponse:
    return await service.list_comments(access, pagination=pagination)


@comments_router.patch(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="Update a comment by ID (Author or Workspace Owner/Admin)",
    responses={
        status.HTTP_200_OK: {"description": "Comment updated successfully"},
        **TASK_WRITE_RESPONSES,
    },
)
async def update_comment(
    data: CommentUpdate,
    access: CommentModifyDep,
    service: TaskServiceDep,
) -> CommentResponse:
    return await service.update_comment(access, data)


@comments_router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a comment by ID (Author or Workspace Owner/Admin)",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Comment deleted successfully"},
        **TASK_WRITE_RESPONSES,
    },
)
async def delete_comment(
    access: CommentModifyDep,
    service: TaskServiceDep,
) -> None:
    await service.delete_comment(access)
