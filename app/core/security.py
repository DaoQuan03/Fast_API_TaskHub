from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4
import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.messages import INVALID_OR_EXPIRED_TOKEN, INVALID_TOKEN_TYPE
from app.models.enums import TokenType

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_token(
    subject: int | str,
    token_type: TokenType,
    expires_delta: timedelta | None = None,
    jti: str | None = None,
) -> tuple[str, str, datetime]:
    now = datetime.now(timezone.utc)
    if expires_delta is None:
        if token_type == TokenType.ACCESS:
            expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        else:
            expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    expire = now + expires_delta
    token_jti = jti or str(uuid4())
    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type.value,
        "jti": token_jti,
        "iat": now,
        "exp": expire,
    }
    encoded = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return encoded, token_jti, expire


def create_access_token(
    subject: int | str,
    expires_delta: timedelta | None = None,
) -> str:
    token, _, _ = create_token(subject, TokenType.ACCESS, expires_delta=expires_delta)
    return token


def create_refresh_token(
    subject: int | str,
    expires_delta: timedelta | None = None,
) -> tuple[str, str, datetime]:
    return create_token(subject, TokenType.REFRESH, expires_delta=expires_delta)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        token_type = payload["type"]
        user_id = int(payload["sub"])
        jti = str(payload["jti"])
        if not jti:
            raise ValueError
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        raise UnauthorizedException(INVALID_OR_EXPIRED_TOKEN)

    if token_type != expected_type.value:
        raise UnauthorizedException(INVALID_TOKEN_TYPE)

    payload["user_id"] = user_id
    return payload
