from typing import Annotated
from fastapi import Depends

from app.core.constants import WORKSPACE_READ_ROLES, WORKSPACE_WRITE_ROLES
from app.core.exceptions import (
    NotFoundException,
    UnprocessableEntityException,
)
from app.core.messages import (
    ASSIGNEE_NOT_IN_WORKSPACE,
    LABEL_NOT_FOUND,
    LABEL_NOT_IN_PROJECT,
    TASK_LABEL_NOT_FOUND,
)
from app.dependencies import (
    CommentAccessContext,
    PaginationParams,
    TaskAccessContext,
    resolve_project_access,
)
from app.models.user import User
from app.repositories.task import TaskRepository, get_task_repository
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


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    async def create_task(
        self,
        data: TaskCreate,
        current_user: User,
    ) -> TaskResponse:
        if data.project_id is not None:
            project_access = await resolve_project_access(
                data.project_id,
                current_user,
                self.repository.session,
                WORKSPACE_WRITE_ROLES,
                require_active=True,
            )
            if data.assignee_id is not None:
                await self._ensure_assignee_in_workspace(
                    project_access.project.workspace_id,
                    data.assignee_id,
                )

        task_dict = data.model_dump()
        task_dict["created_by"] = current_user.id
        created = await self.repository.create(**task_dict)
        return TaskResponse.model_validate(created)

    async def list_tasks(
        self,
        *,
        current_user: User,
        pagination: PaginationParams,
        filters: TaskFilterParams,
    ) -> TaskListResponse:
        if filters.project_id is not None:
            await resolve_project_access(
                filters.project_id,
                current_user,
                self.repository.session,
                WORKSPACE_READ_ROLES,
                require_active=False,
            )

        items, total = await self.repository.get_filtered_tasks(
            current_user=current_user,
            pagination=pagination,
            filters=filters,
        )
        return TaskListResponse(
            items=[TaskResponse.model_validate(item) for item in items],
            total=total,
        )

    async def get_task(self, access: TaskAccessContext) -> TaskResponse:
        return TaskResponse.model_validate(access.task)

    async def update_task(
        self,
        access: TaskAccessContext,
        data: TaskUpdate,
    ) -> TaskResponse:
        update_data = data.model_dump(exclude_unset=True)
        target_project = access.project

        if "project_id" in update_data and update_data["project_id"] is not None:
            new_proj_access = await resolve_project_access(
                update_data["project_id"],
                access.current_user,
                self.repository.session,
                WORKSPACE_WRITE_ROLES,
                require_active=True,
            )
            target_project = new_proj_access.project

        target_assignee_id = update_data.get("assignee_id", access.task.assignee_id)
        if target_project is not None and target_assignee_id is not None:
            await self._ensure_assignee_in_workspace(
                target_project.workspace_id,
                target_assignee_id,
            )

        updated = await self.repository.update(access.task, update_data)
        return TaskResponse.model_validate(updated)

    async def delete_task(
        self,
        access: TaskAccessContext,
    ) -> None:
        await self.repository.delete(access.task)

    async def attach_label(
        self,
        access: TaskAccessContext,
        label_id: int,
    ) -> TaskResponse:
        label = await self.repository.get_label_by_id(label_id)
        if not label:
            raise NotFoundException(LABEL_NOT_FOUND.format(label_id=label_id))

        if access.task.project_id is None or label.project_id != access.task.project_id:
            raise UnprocessableEntityException(LABEL_NOT_IN_PROJECT)

        updated_task = await self.repository.attach_label(access.task.id, label_id)
        return TaskResponse.model_validate(updated_task)

    async def detach_label(
        self,
        access: TaskAccessContext,
        label_id: int,
    ) -> None:
        removed = await self.repository.detach_label(access.task.id, label_id)
        if not removed:
            raise NotFoundException(
                TASK_LABEL_NOT_FOUND.format(
                    label_id=label_id,
                    task_id=access.task.id,
                )
            )

    async def create_comment(
        self,
        access: TaskAccessContext,
        data: CommentCreate,
    ) -> CommentResponse:
        comment = await self.repository.create_comment(
            task_id=access.task.id,
            author_id=access.current_user.id,
            content=data.content,
        )
        return CommentResponse.model_validate(comment)

    async def list_comments(
        self,
        access: TaskAccessContext,
        pagination: PaginationParams,
    ) -> CommentListResponse:
        items, total = await self.repository.list_comments(
            access.task.id,
            pagination=pagination,
        )
        return CommentListResponse(
            items=[CommentResponse.model_validate(item) for item in items],
            total=total,
        )

    async def update_comment(
        self,
        access: CommentAccessContext,
        data: CommentUpdate,
    ) -> CommentResponse:
        updated = await self.repository.update_comment(
            access.comment,
            data.content,
        )
        return CommentResponse.model_validate(updated)

    async def delete_comment(
        self,
        access: CommentAccessContext,
    ) -> None:
        await self.repository.delete_comment(access.comment)

    async def _ensure_assignee_in_workspace(
        self,
        workspace_id: int,
        assignee_id: int,
    ) -> None:
        is_member = await self.repository.is_workspace_member(
            workspace_id,
            assignee_id,
        )
        if not is_member:
            raise UnprocessableEntityException(ASSIGNEE_NOT_IN_WORKSPACE)


def get_task_service(
    repository: Annotated[TaskRepository, Depends(get_task_repository)],
) -> TaskService:
    return TaskService(repository=repository)
