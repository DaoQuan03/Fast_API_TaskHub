from datetime import datetime, timezone
from pydantic import Field, field_validator, model_validator

from app.core.constants import TASK_TITLE_MAX_LENGTH, TASK_TITLE_MIN_LENGTH
from app.core.messages import DUE_DATE_IN_PAST,FIELD_CANNOT_BE_NULL
from app.models.enums import TaskPriority, TaskStatus
from app.schemas.base import BaseSchema

def _validate_due_date_not_pass(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    now = datetime.now(timezone.utc)
    compare_val = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    if compare_val < now:
        raise ValueError(DUE_DATE_IN_PAST)
    return value

class TaskBase(BaseSchema):
    title: str = Field(
        ...,
        min_length = TASK_TITLE_MIN_LENGTH,
        max_length = TASK_TITLE_MAX_LENGTH,
        description = "Tieu de"
    )
    priority: TaskPriority = Field(
        default = TaskPriority.MEDIUM,
        description = "Muc do uu tien"
    )
    due_date: datetime | None = Field(
        default = None,
        description = "Dealine"
    )
    project_id: int | None = Field(
        default = None,
        description="ID cua du an"
    )
    assignee_id: int | None = Field(
        default = None,
        description="ID cua nguoi duoc giao viec"
    )

class TaskCreate(TaskBase):
    @field_validator("due_date")
    @classmethod
    def check_due_date(cls, value: datetime | None) -> datetime | None:
        return _validate_due_date_not_pass(value)

class TaskUpdate(BaseSchema):
    title: str | None = Field(
        default = None,
        min_length = TASK_TITLE_MIN_LENGTH,
        max_length = TASK_TITLE_MAX_LENGTH,
        description = "Tieu de cua task"
    )
    status: TaskStatus | None = Field(default = None, description = "Trang thai task")
    priority: TaskPriority | None = Field(default=None, description = "Muc do uu tien")
    due_date: datetime | None = Field(default = None, description = "dealine")
    assignee_id: int | None = Field(default = None, description = "ID nguoi duoc phan cong")
    project_id: int | None = Field(default = None, description = "ID du an")

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_non_nullable_feilds(cls, data: object) -> object:
        if isinstance(data, dict):
            for field in ("title", "status", "priority"):
                if field in data and data[field] is None:
                    raise ValueError(FIELD_CANNOT_BE_NULL.format(field=field))
        return data
    
    @field_validator("due_date")
    @classmethod
    def check_due_date(cls, value: datetime | None) -> datetime | None :
        return _validate_due_date_not_pass(value)

class TaskResponse(TaskBase):
    id: int
    status: TaskStatus = Field(default = TaskStatus.TODO, description = "Trang thai cua task")
    created_by : int | None = None
    created_at: datetime

class TaskListResponse(BaseSchema):
    items: list[TaskResponse]
    total: int