from typing import Annotated, Any
from fastapi import Depends
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.exceptions import ConflictException
from app.core.messages import TASK_LABEL_ALREADY_ATTACHED
from app.dependencies import PaginationParams
from app.models.comment import Comment
from app.models.enums import UserRole
from app.models.label import Label, TaskLabel
from app.models.project import Project
from app.models.task import Task
from app.models.user import User
from app.models.workspace import WorkspaceMember
from app.repositories.base import BaseRepository
from app.schemas.task import TaskFilterParams


class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Task, session)

    async def create(self, **data: Any) -> Task:
        obj = self.model(**data)
        self.session.add(obj)
        await self.session.flush()
        stmt = (
            select(Task)
            .options(selectinload(Task.labels))
            .where(Task.id == obj.id)
        )
        loaded = await self.session.scalar(stmt)
        return loaded or obj

    async def update(self, obj: Task, data: dict[str, Any]) -> Task:
        for field, value in data.items():
            setattr(obj, field, value)
        await self.session.flush()
        stmt = (
            select(Task)
            .options(selectinload(Task.labels))
            .where(Task.id == obj.id)
        )
        loaded = await self.session.scalar(stmt)
        return loaded or obj

    async def get_filtered_tasks(
        self,
        *,
        current_user: User,
        pagination: PaginationParams,
        filters: TaskFilterParams,
    ) -> tuple[list[Task], int]:
        conditions: list[Any] = []
        if filters.project_id is not None:
            conditions.append(Task.project_id == filters.project_id)
        if filters.status:
            conditions.append(Task.status.in_(filters.status))
        if filters.priority:
            conditions.append(Task.priority.in_(filters.priority))
        if filters.assignee_id is not None:
            conditions.append(Task.assignee_id == filters.assignee_id)

        if current_user.role != UserRole.ADMIN and filters.project_id is None:
            member_project_ids = (
                select(Project.id)
                .join(
                    WorkspaceMember,
                    WorkspaceMember.workspace_id == Project.workspace_id,
                )
                .where(WorkspaceMember.user_id == current_user.id)
            )
            conditions.append(
                or_(
                    Task.project_id.in_(member_project_ids),
                    (Task.project_id.is_(None))
                    & (
                        (Task.created_by == current_user.id)
                        | (Task.assignee_id == current_user.id)
                    ),
                )
            )

        count_stmt = select(func.count()).select_from(Task)
        list_stmt = select(Task).options(selectinload(Task.labels))
        if conditions:
            count_stmt = count_stmt.where(*conditions)
            list_stmt = list_stmt.where(*conditions)

        total = await self.session.scalar(count_stmt)
        list_stmt = (
            list_stmt.order_by(Task.created_at.asc(), Task.id.asc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await self.session.scalars(list_stmt)
        return list(result.all()), total or 0

    async def is_workspace_member(
        self,
        workspace_id: int,
        user_id: int,
    ) -> bool:
        stmt = select(WorkspaceMember.user_id).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
        return (await self.session.scalar(stmt)) is not None

    async def get_label_by_id(self, label_id: int) -> Label | None:
        return await self.session.get(Label, label_id)

    async def attach_label(self, task_id: int, label_id: int) -> Task:
        link = TaskLabel(task_id=task_id, label_id=label_id)
        self.session.add(link)
        try:
            await self.session.flush()
        except IntegrityError:
            await self.session.rollback()
            raise ConflictException(TASK_LABEL_ALREADY_ATTACHED)

        stmt = (
            select(Task)
            .options(selectinload(Task.labels))
            .where(Task.id == task_id)
            .execution_options(populate_existing=True)
        )
        task = await self.session.scalar(stmt)
        assert task is not None
        return task

    async def detach_label(self, task_id: int, label_id: int) -> bool:
        stmt = delete(TaskLabel).where(
            TaskLabel.task_id == task_id,
            TaskLabel.label_id == label_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return (result.rowcount or 0) > 0

    async def create_comment(
        self,
        *,
        task_id: int,
        author_id: int,
        content: str,
    ) -> Comment:
        comment = Comment(
            task_id=task_id,
            author_id=author_id,
            content=content,
        )
        self.session.add(comment)
        await self.session.flush()
        await self.session.refresh(comment)
        return comment

    async def list_comments(
        self,
        task_id: int,
        pagination: PaginationParams,
    ) -> tuple[list[Comment], int]:
        count_stmt = (
            select(func.count())
            .select_from(Comment)
            .where(Comment.task_id == task_id)
        )
        total = await self.session.scalar(count_stmt)
        stmt = (
            select(Comment)
            .where(Comment.task_id == task_id)
            .order_by(Comment.created_at.asc(), Comment.id.asc())
            .offset(pagination.offset)
            .limit(pagination.limit)
        )
        result = await self.session.scalars(stmt)
        return list(result.all()), total or 0

    async def update_comment(
        self,
        comment: Comment,
        content: str,
    ) -> Comment:
        comment.content = content
        await self.session.flush()
        await self.session.refresh(comment)
        return comment

    async def delete_comment(self, comment: Comment) -> None:
        await self.session.delete(comment)
        await self.session.flush()


def get_task_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskRepository:
    return TaskRepository(session=session)
