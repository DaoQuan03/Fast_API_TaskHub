from datetime import datetime
from pydantic import EmailStr, Field, field_validator, model_validator

from app.core.constants import (
    EMAIL_MAX_LENGTH,
    NAME_MAX_LENGTH,
    NAME_MIN_LENGTH,
    NON_EMPTY_STR_MIN_LENGTH,
    PASSWORD_MAX_BYTES,
    PASSWORD_MIN_LENGTH,
    TOKEN_TYPE_BEARER,
)
from app.core.messages import FIELD_CANNOT_BE_NULL, PASSWORD_TOO_LONG_BYTES
from app.models.enums import UserRole
from app.schemas.base import BaseSchema


def validate_password_bytes(value: str) -> str:
    if len(value.encode("utf-8")) > PASSWORD_MAX_BYTES:
        raise ValueError(PASSWORD_TOO_LONG_BYTES.format(max_bytes=PASSWORD_MAX_BYTES))
    return value


def normalize_email_str(value: object) -> object:
    if isinstance(value, str):
        return value.strip().lower()
    return value


class RegisterRequest(BaseSchema):
    email: EmailStr = Field(..., max_length=EMAIL_MAX_LENGTH)
    full_name: str = Field(
        ...,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
    )
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_BYTES,
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return normalize_email_str(value)

    @field_validator("password")
    @classmethod
    def check_password_bytes(cls, value: str) -> str:
        return validate_password_bytes(value)


class LoginRequest(BaseSchema):
    email: EmailStr = Field(..., max_length=EMAIL_MAX_LENGTH)
    password: str = Field(
        ...,
        min_length=NON_EMPTY_STR_MIN_LENGTH,
        max_length=PASSWORD_MAX_BYTES,
    )

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return normalize_email_str(value)

    @field_validator("password")
    @classmethod
    def check_password_bytes(cls, value: str) -> str:
        return validate_password_bytes(value)


class TokenResponse(BaseSchema):
    access_token: str
    refresh_token: str
    token_type: str = TOKEN_TYPE_BEARER


class RefreshRequest(BaseSchema):
    refresh_token: str = Field(..., min_length=NON_EMPTY_STR_MIN_LENGTH)


class ChangePasswordRequest(BaseSchema):
    current_password: str = Field(
        ...,
        min_length=NON_EMPTY_STR_MIN_LENGTH,
        max_length=PASSWORD_MAX_BYTES,
    )
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_BYTES,
    )

    @field_validator("current_password", "new_password")
    @classmethod
    def check_password_bytes(cls, value: str) -> str:
        return validate_password_bytes(value)


class UserResponse(BaseSchema):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class UserMeUpdate(BaseSchema):
    full_name: str | None = Field(
        default=None,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
    )

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_non_nullable_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            if "full_name" in data and data["full_name"] is None:
                raise ValueError(FIELD_CANNOT_BE_NULL.format(field="full_name"))
        return data


class UserUpdate(BaseSchema):
    full_name: str | None = Field(
        default=None,
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
    )
    role: UserRole | None = None
    is_active: bool | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_non_nullable_fields(cls, data: object) -> object:
        if isinstance(data, dict):
            for field in ("full_name", "role", "is_active"):
                if field in data and data[field] is None:
                    raise ValueError(FIELD_CANNOT_BE_NULL.format(field=field))
        return data
