from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.core.constants import DEFAULT_LIMIT, DEFAULT_PAGE, MAX_LIMIT
from app.core.database import get_db
from app.core.security import decode_token
from app.models.enums import TokenType
from app.models.user import User
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate
from app.services.task import TaskService, get_task_service
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

TaskServiceDep = Annotated[TaskService, Depends(get_task_service)]
optional_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)


async def get_optional_current_user(
    token: Annotated[str | None, Depends(optional_oauth2)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    if not token:
        return None
    payload = decode_token(token, expected_type=TokenType.ACCESS)
    return await session.get(User, payload["user_id"])


OptionalUserDep = Annotated[User | None, Depends(get_optional_current_user)]

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
async def create_task(
    data: TaskCreate,
    service: TaskServiceDep,
    current_user: OptionalUserDep = None,
) -> TaskResponse:
    return await service.create_task(data, current_user=current_user)


@router.get(
    "",
    response_model=TaskListResponse,
    summary="List all tasks with pagination",
    responses={
        status.HTTP_200_OK: {"description": "List of tasks retrieved successfully"},
    },
)
async def list_tasks(
    service: TaskServiceDep,
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
        **NOT_FOUND_RESPONSE,
    },
)
async def get_task(task_id: int, service: TaskServiceDep) -> TaskResponse:
    return await service.get_task(task_id)


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
async def update_task(
    task_id: int,
    data: TaskUpdate,
    service: TaskServiceDep,
    current_user: OptionalUserDep = None,
) -> TaskResponse:
    return await service.update_task(task_id, data, current_user=current_user)


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task by ID",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Task deleted successfully"},
        **NOT_FOUND_RESPONSE,
    },
)
async def delete_task(
    task_id: int,
    service: TaskServiceDep,
    current_user: OptionalUserDep = None,
) -> None:
    await service.delete_task(task_id, current_user=current_user)
