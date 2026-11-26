from typing import Annotated
from fastapi import Depends

from app.core.constants import DEFAULT_LIMIT, DEFAULT_PAGE
from app.core.exceptions import NotFoundException
from app.core.messages import TASK_NOT_FOUND
from app.models.task import Task
from app.models.user import User
from app.repositories.task import TaskRepository, get_task_repository
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    async def create_task(
        self,
        data: TaskCreate,
        current_user: User,
    ) -> TaskResponse:
        task_dict = data.model_dump()
        task_dict["created_by"] = current_user.id
        created = await self.repository.create(**task_dict)
        return TaskResponse.model_validate(created)

    async def list_tasks(
        self,
        *,
        page: int = DEFAULT_PAGE,
        limit: int = DEFAULT_LIMIT,
    ) -> TaskListResponse:
        items, total = await self.repository.get_multi(page=page, limit=limit)
        return TaskListResponse(
            items=[TaskResponse.model_validate(item) for item in items],
            total=total,
        )

    async def get_task(self, task_id: int) -> TaskResponse:
        task = await self.repository.get(task_id)
        if not task:
            raise NotFoundException(TASK_NOT_FOUND.format(task_id=task_id))
        return TaskResponse.model_validate(task)

    async def update_task(
        self,
        task: Task,
        data: TaskUpdate,
    ) -> TaskResponse:
        update_data = data.model_dump(exclude_unset=True)
        updated = await self.repository.update(task, update_data)
        return TaskResponse.model_validate(updated)

    async def delete_task(
        self,
        task: Task,
    ) -> None:
        await self.repository.delete(task)


def get_task_service(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    return TaskService(repository=repository)
