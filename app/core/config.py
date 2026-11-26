from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import (
    DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES,
    DEFAULT_JWT_ALGORITHM,
    DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS,
    SECRET_KEY_MIN_LENGTH,
)
from app.core.messages import SECRET_KEY_TOO_SHORT


class Settings(BaseSettings):
    PROJECT_NAME: str = "FastAPI TaskHub"
    DEBUG: bool = True
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "sqlite+aiosqlite:///./taskhub.db"
    SECRET_KEY: str = Field(..., min_length=SECRET_KEY_MIN_LENGTH)
    JWT_ALGORITHM: str = DEFAULT_JWT_ALGORITHM
    ACCESS_TOKEN_EXPIRE_MINUTES: int = DEFAULT_ACCESS_TOKEN_EXPIRE_MINUTES
    REFRESH_TOKEN_EXPIRE_DAYS: int = DEFAULT_REFRESH_TOKEN_EXPIRE_DAYS

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v: object) -> bool:
        if isinstance(v, str):
            if v.lower() in ("true", "1", "yes", "t", "dev", "development"):
                return True
            if v.lower() in ("false", "0", "no", "f", "release", "prod", "production"):
                return False
        return bool(v)

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v: object) -> str:
        if not isinstance(v, str) or len(v.strip()) < SECRET_KEY_MIN_LENGTH:
            raise ValueError(
                SECRET_KEY_TOO_SHORT.format(min_length=SECRET_KEY_MIN_LENGTH)
            )
        return v.strip()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
