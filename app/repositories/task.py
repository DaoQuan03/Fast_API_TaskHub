from typing import Annotated
from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import DEFAULT_PAGE, DEFAULT_LIMIT, MAX_LIMIT
from app.core.database import get_db
from app.models.task import Task
from app.repositories.base import BaseRepository


class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Task, session)

    async def get_multi(
        self, *, page: int = DEFAULT_PAGE, limit: int = DEFAULT_LIMIT
    ) -> tuple[list[Task], int]:
        total = await self.session.scalar(select(func.count()).select_from(Task))
        stmt = (
            select(Task)
            .order_by(Task.created_at.asc(), Task.id.asc())
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await self.session.scalars(stmt)
        return list(result.all()), total or 0


def get_task_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TaskRepository:
    return TaskRepository(session=session)
