from typing import Annotated
from fastapi import Depends

from app.core.exceptions import NotFoundException
from app.core.messages import TASK_NOT_FOUND
from app.repositories.task import TaskRepository, get_task_repository
from app.schemas.task import TaskCreate, TaskListResponse, TaskResponse, TaskUpdate


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def create_task(self, data: TaskCreate) -> TaskResponse:
        task_dict = data.model_dump()
        created = self.repository.create(task_dict)
        return TaskResponse.model_validate(created)

    def list_tasks(self) -> TaskListResponse:
        items, total = self.repository.get_all()
        return TaskListResponse(
            items=[TaskResponse.model_validate(item) for item in items],
            total=total,
        )

    def get_task(self, task_id: int) -> TaskResponse:
        task = self.repository.get_by_id(task_id)
        if not task:
            raise NotFoundException(TASK_NOT_FOUND.format(task_id=task_id))
        return TaskResponse.model_validate(task)

    def update_task(self, task_id: int, data: TaskUpdate) -> TaskResponse:
        update_data = data.model_dump(exclude_unset=True)
        updated = self.repository.update(task_id, update_data)
        if not updated:
            raise NotFoundException(TASK_NOT_FOUND.format(task_id=task_id))
        return TaskResponse.model_validate(updated)

    def delete_task(self, task_id: int) -> None:
        deleted = self.repository.delete(task_id)
        if not deleted:
            raise NotFoundException(TASK_NOT_FOUND.format(task_id=task_id))


def get_task_service(
    repository: Annotated[TaskRepository, Depends(get_task_repository)]
) -> TaskService:
    return TaskService(repository=repository)