from datetime import datetime
from pydantic import Field, model_validator

from app.core.constants import NAME_MAX_LENGTH, NAME_MIN_LENGTH
from app.core.messages import FIELD_CANNOT_BE_NULL
from app.models.enums import WorkspaceRole
from app.schemas.base import BaseSchema


class WorkspaceBase(BaseSchema):
    name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
    )


class WorkspaceCreate(WorkspaceBase):
    pass


class WorkspaceUpdate(BaseSchema):
    name: str | None = Field(
        default=None,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_non_nullable_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            if "name" in data and data["name"] is None:
                raise ValueError(FIELD_CANNOT_BE_NULL.format(field="name"))
        return data


class WorkspaceResponse(WorkspaceBase):
    id: int
    owner_id: int
    created_at: datetime


class WorkspaceListResponse(BaseSchema):
    items: list[WorkspaceResponse]
    total: int


class WorkspaceMemberCreate(BaseSchema):
    user_id: int = Field(..., ge=1)
    role: WorkspaceRole = Field(default=WorkspaceRole.VIEWER)


class WorkspaceMemberUpdate(BaseSchema):
    role: WorkspaceRole

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_non_nullable_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            if "role" in data and data["role"] is None:
                raise ValueError(FIELD_CANNOT_BE_NULL.format(field="role"))
        return data


class WorkspaceMemberResponse(BaseSchema):
    workspace_id: int
    user_id: int
    role: WorkspaceRole


class WorkspaceMemberListResponse(BaseSchema):
    items: list[WorkspaceMemberResponse]
    total: int
