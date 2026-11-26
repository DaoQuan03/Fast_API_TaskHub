from typing import Annotated
from fastapi import APIRouter, Depends, Query, status

from app.core.constants import DEFAULT_LIMIT, DEFAULT_PAGE, MAX_LIMIT
from app.dependencies import CurrentUserDep, OwnedTaskDep
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
from app.services.task import TaskService, get_task_service

router = APIRouter()

TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]

AUTH_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
}
NOT_FOUND_RESPONSE = {
    status.HTTP_404_NOT_FOUND: {"description": "Task not found"},
}
FORBIDDEN_RESPONSE = {
    status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
}


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
    responses={
        status.HTTP_201_CREATED: {"description": "Task created successfully"},
        **AUTH_RESPONSES,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
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
    summary="List all tasks with pagination",
    responses={
        status.HTTP_200_OK: {"description": "List of tasks retrieved successfully"},
        **AUTH_RESPONSES,
    },
)
async def list_tasks(
    service: TaskServiceDep,
    _current_user: CurrentUserDep,
    page: Annotated[int, Query(ge=DEFAULT_PAGE, description="Page number")] = DEFAULT_PAGE,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Items per page")] = DEFAULT_LIMIT,
) -> TaskListResponse:
    return await service.list_tasks(page=page, limit=limit)


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get a task by ID",
    responses={
        status.HTTP_200_OK: {"description": "Task retrieved successfully"},
        **AUTH_RESPONSES,
        **NOT_FOUND_RESPONSE,
    },
)
async def get_task(
    task_id: int,
    service: TaskServiceDep,
    _current_user: CurrentUserDep,
) -> TaskResponse:
    return await service.get_task(task_id)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update a task by ID",
    responses={
        status.HTTP_200_OK: {"description": "Task updated successfully"},
        **AUTH_RESPONSES,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
    },
)
async def update_task(
    data: TaskUpdate,
    task: OwnedTaskDep,
    service: TaskServiceDep,
) -> TaskResponse:
    return await service.update_task(task, data)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task by ID",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Task deleted successfully"},
        **AUTH_RESPONSES,
        **FORBIDDEN_RESPONSE,
        **NOT_FOUND_RESPONSE,
    },
)
async def delete_task(
    task: OwnedTaskDep,
    service: TaskServiceDep,
) -> None:
    await service.delete_task(task)
