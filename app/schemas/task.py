from datetime import datetime, timezone
from pydantic import Field, PositiveInt, field_validator, model_validator

from app.core.constants import (
    NON_EMPTY_STR_MIN_LENGTH,
    TASK_TITLE_MAX_LENGTH,
    TASK_TITLE_MIN_LENGTH,
)
from app.core.messages import DUE_DATE_IN_PAST, FIELD_CANNOT_BE_NULL
from app.models.enums import TaskPriority, TaskStatus
from app.schemas.base import BaseSchema
from app.schemas.workspace import LabelResponse


def _validate_due_date_not_past(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    now = datetime.now(timezone.utc)
    compare_val = (
        value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    )
    if compare_val < now:
        raise ValueError(DUE_DATE_IN_PAST)
    return value


class TaskBase(BaseSchema):
    title: str = Field(
        ...,
        min_length=TASK_TITLE_MIN_LENGTH,
        max_length=TASK_TITLE_MAX_LENGTH,
        description="Tiêu đề task",
    )
    description: str | None = Field(default=None, description="Mô tả chi tiết")
    priority: TaskPriority = Field(
        default=TaskPriority.MEDIUM,
        description="Mức độ ưu tiên",
    )
    due_date: datetime | None = Field(
        default=None,
        description="Hạn chót hoàn thành",
    )
    project_id: PositiveInt | None = Field(
        default=None,
        description="ID dự án liên kết",
    )
    assignee_id: PositiveInt | None = Field(
        default=None,
        description="ID người được phân công",
    )


class TaskCreate(TaskBase):
    @field_validator("due_date")
    @classmethod
    def check_due_date(cls, value: datetime | None) -> datetime | None:
        return _validate_due_date_not_past(value)


class TaskUpdate(BaseSchema):
    title: str | None = Field(
        default=None,
        min_length=TASK_TITLE_MIN_LENGTH,
        max_length=TASK_TITLE_MAX_LENGTH,
        description="Tiêu đề task",
    )
    description: str | None = Field(default=None, description="Mô tả chi tiết")
    status: TaskStatus | None = Field(default=None, description="Trạng thái task")
    priority: TaskPriority | None = Field(default=None, description="Mức độ ưu tiên")
    due_date: datetime | None = Field(default=None, description="Hạn chót hoàn thành")
    assignee_id: PositiveInt | None = Field(
        default=None,
        description="ID người được phân công",
    )
    project_id: PositiveInt | None = Field(
        default=None,
        description="ID dự án",
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_non_nullable_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            for field in ("title", "status", "priority"):
                if field in data and data[field] is None:
                    raise ValueError(FIELD_CANNOT_BE_NULL.format(field=field))
        return data

    @field_validator("due_date")
    @classmethod
    def check_due_date(cls, value: datetime | None) -> datetime | None:
        return _validate_due_date_not_past(value)


class TaskResponse(TaskBase):
    id: int
    status: TaskStatus = Field(default=TaskStatus.TODO, description="Trạng thái task")
    created_by: int | None = None
    created_at: datetime
    labels: list[LabelResponse] = Field(default_factory=list)


class TaskListResponse(BaseSchema):
    items: list[TaskResponse]
    total: int


class TaskFilterParams(BaseSchema):
    status: list[TaskStatus] | None = None
    priority: list[TaskPriority] | None = None
    assignee_id: PositiveInt | None = None
    project_id: PositiveInt | None = None


class CommentCreate(BaseSchema):
    content: str = Field(..., min_length=NON_EMPTY_STR_MIN_LENGTH)


class CommentUpdate(BaseSchema):
    content: str = Field(..., min_length=NON_EMPTY_STR_MIN_LENGTH)

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_non_nullable_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            if "content" in data and data["content"] is None:
                raise ValueError(FIELD_CANNOT_BE_NULL.format(field="content"))
        return data


class CommentResponse(BaseSchema):
    id: int
    task_id: int
    author_id: int
    content: str
    created_at: datetime


class CommentListResponse(BaseSchema):
    items: list[CommentResponse]
    total: int
