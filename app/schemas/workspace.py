from datetime import datetime
from pydantic import Field, PositiveInt, field_validator, model_validator

from app.core.constants import (
    COLOR_MAX_LENGTH,
    DEFAULT_LABEL_COLOR,
    LABEL_NAME_MAX_LENGTH,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
    WORKSPACE_ASSIGNABLE_ROLES,
)
from app.core.messages import CANNOT_ASSIGN_OWNER_ROLE, FIELD_CANNOT_BE_NULL
from app.models.enums import ProjectStatus, WorkspaceRole
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
    user_id: PositiveInt
    role: WorkspaceRole = Field(default=WorkspaceRole.VIEWER)

    @field_validator("role")
    @classmethod
    def reject_owner_role(cls, value: WorkspaceRole) -> WorkspaceRole:
        if value not in WORKSPACE_ASSIGNABLE_ROLES:
            raise ValueError(CANNOT_ASSIGN_OWNER_ROLE)
        return value


class WorkspaceMemberUpdate(BaseSchema):
    role: WorkspaceRole

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_non_nullable_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            if "role" in data and data["role"] is None:
                raise ValueError(FIELD_CANNOT_BE_NULL.format(field="role"))
        return data

    @field_validator("role")
    @classmethod
    def reject_owner_role(cls, value: WorkspaceRole) -> WorkspaceRole:
        if value not in WORKSPACE_ASSIGNABLE_ROLES:
            raise ValueError(CANNOT_ASSIGN_OWNER_ROLE)
        return value


class WorkspaceMemberResponse(BaseSchema):
    workspace_id: int
    user_id: int
    role: WorkspaceRole


class WorkspaceMemberListResponse(BaseSchema):
    items: list[WorkspaceMemberResponse]
    total: int


class ProjectCreate(BaseSchema):
    name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
    )
    description: str | None = None


class ProjectUpdate(BaseSchema):
    name: str | None = Field(
        default=None,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
    )
    description: str | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_non_nullable_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            if "name" in data and data["name"] is None:
                raise ValueError(FIELD_CANNOT_BE_NULL.format(field="name"))
        return data


class ProjectResponse(BaseSchema):
    id: int
    workspace_id: int
    name: str
    description: str | None = None
    status: ProjectStatus
    created_at: datetime


class ProjectListResponse(BaseSchema):
    items: list[ProjectResponse]
    total: int


class LabelCreate(BaseSchema):
    name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=LABEL_NAME_MAX_LENGTH,
    )
    color: str = Field(
        default=DEFAULT_LABEL_COLOR,
        min_length=NAME_MIN_LENGTH,
        max_length=COLOR_MAX_LENGTH,
    )


class LabelUpdate(BaseSchema):
    name: str | None = Field(
        default=None,
        min_length=NAME_MIN_LENGTH,
        max_length=LABEL_NAME_MAX_LENGTH,
    )
    color: str | None = Field(
        default=None,
        min_length=NAME_MIN_LENGTH,
        max_length=COLOR_MAX_LENGTH,
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_non_nullable_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            for field in ("name", "color"):
                if field in data and data[field] is None:
                    raise ValueError(FIELD_CANNOT_BE_NULL.format(field=field))
        return data


class LabelResponse(BaseSchema):
    id: int
    project_id: int
    name: str
    color: str


class LabelListResponse(BaseSchema):
    items: list[LabelResponse]
    total: int
