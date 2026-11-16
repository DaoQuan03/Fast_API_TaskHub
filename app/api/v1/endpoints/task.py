from typing import Annotated
from fastapi import APIRouter, Depends, status

from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
from app.services.task import TaskService, get_task_service

router = APIRouter()

TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]

NOT_FOUND_RESPONSE = {
    status.HTTP_404_NOT_FOUND: {"description": "Task not found"},
}


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new task",
    responses={
        status.HTTP_201_CREATED: {"description": "Task created successfully"},
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
    },
)
def create_task(data: TaskCreate, service: TaskServiceDep) -> TaskResponse:
    return service.create_task(data)


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List all tasks",
    responses={
        status.HTTP_200_OK: {"description": "List of tasks retrieved successfully"},
    },
)
def list_tasks(service: TaskServiceDep) -> TaskListResponse:
    return service.list_tasks()


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Get a task by ID",
    responses={
        status.HTTP_200_OK: {"description": "Task retrieved successfully"},
        **NOT_FOUND_RESPONSE,
    },
)
def get_task(task_id: int, service: TaskServiceDep) -> TaskResponse:
    return service.get_task(task_id)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update a task by ID",
    responses={
        status.HTTP_200_OK: {"description": "Task updated successfully"},
        **NOT_FOUND_RESPONSE,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
    },
)
def update_task(
    task_id: int, data: TaskUpdate, service: TaskServiceDep
) -> TaskResponse:
    return service.update_task(task_id, data)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task by ID",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Task deleted successfully"},
        **NOT_FOUND_RESPONSE,
    },
)
def delete_task(task_id: int, service: TaskServiceDep) -> None:
    service.delete_task(task_id)