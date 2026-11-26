from datetime import datetime, timezone
from typing import Annotated
from fastapi import Depends

from app.core.constants import DUMMY_PASSWORD_HASH
from app.core.exceptions import (
    BadRequestException,
    NotFoundException,
    UnauthorizedException,
)
from app.core.messages import (
    CANNOT_DELETE_SELF,
    CANNOT_MODIFY_OWN_ROLE_OR_STATUS,
    INACTIVE_USER,
    INCORRECT_CURRENT_PASSWORD,
    INVALID_CREDENTIALS,
    INVALID_OR_EXPIRED_TOKEN,
    LAST_ACTIVE_ADMIN_REQUIRED,
    TOKEN_REVOKED_OR_REUSED,
    USER_NOT_FOUND,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.enums import TokenType, UserRole
from app.models.user import User
from app.repositories.user import UserRepository, get_user_repository
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserMeUpdate,
    UserResponse,
    UserUpdate,
)


class AuthService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    async def register(self, data: RegisterRequest) -> UserResponse:
        user = await self.repository.create_user(
            email=str(data.email),
            full_name=data.full_name,
            hashed_password=hash_password(data.password),
            role=UserRole.MEMBER,
        )
        return UserResponse.model_validate(user)

    async def login(self, data: LoginRequest) -> TokenResponse:
        user = await self.repository.get_by_email(str(data.email))
        target_hash = user.hashed_password if user is not None else DUMMY_PASSWORD_HASH
        password_valid = verify_password(data.password, target_hash)
        if user is None or not password_valid:
            raise UnauthorizedException(INVALID_CREDENTIALS)
        if not user.is_active:
            raise UnauthorizedException(INACTIVE_USER)

        return await self._issue_tokens(user.id)

    async def refresh_tokens(self, refresh_token_str: str) -> TokenResponse:
        payload = decode_token(refresh_token_str, expected_type=TokenType.REFRESH)
        jti = payload["jti"]
        user_id = payload["user_id"]

        stored_token = await self.repository.get_refresh_token_by_jti(jti)
        if not stored_token:
            raise UnauthorizedException(INVALID_OR_EXPIRED_TOKEN)

        if stored_token.revoked:
            await self.repository.revoke_all_user_tokens(user_id)
            await self.repository.session.commit()
            raise UnauthorizedException(TOKEN_REVOKED_OR_REUSED)

        expires_at = stored_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise UnauthorizedException(INVALID_OR_EXPIRED_TOKEN)

        revoked_ok = await self.repository.atomic_revoke_refresh_token(jti)
        if not revoked_ok:
            await self.repository.revoke_all_user_tokens(user_id)
            await self.repository.session.commit()
            raise UnauthorizedException(TOKEN_REVOKED_OR_REUSED)

        user = await self.repository.get(user_id)
        if not user:
            raise UnauthorizedException(INVALID_OR_EXPIRED_TOKEN)
        if not user.is_active:
            raise UnauthorizedException(INACTIVE_USER)

        return await self._issue_tokens(user.id)

    async def logout(self, refresh_token_str: str) -> None:
        payload = decode_token(refresh_token_str, expected_type=TokenType.REFRESH)
        jti = payload["jti"]
        stored_token = await self.repository.get_refresh_token_by_jti(jti)
        if not stored_token or stored_token.revoked:
            raise UnauthorizedException(INVALID_OR_EXPIRED_TOKEN)
        await self.repository.atomic_revoke_refresh_token(jti)

    async def change_password(
        self,
        current_user: User,
        data: ChangePasswordRequest,
    ) -> None:
        if not verify_password(data.current_password, current_user.hashed_password):
            raise BadRequestException(INCORRECT_CURRENT_PASSWORD)

        now = datetime.now(timezone.utc)
        await self.repository.update(
            current_user,
            {
                "hashed_password": hash_password(data.new_password),
                "password_changed_at": now,
            },
        )
        await self.repository.revoke_all_user_tokens(current_user.id)

    async def update_me(
        self,
        current_user: User,
        data: UserMeUpdate,
    ) -> UserResponse:
        update_data = data.model_dump(exclude_unset=True)
        updated = await self.repository.update(current_user, update_data)
        return UserResponse.model_validate(updated)

    async def update_user_by_admin(
        self,
        target_user_id: int,
        data: UserUpdate,
        current_admin: User,
    ) -> UserResponse:
        update_data = data.model_dump(exclude_unset=True)
        if current_admin.id == target_user_id and (
            "role" in update_data or "is_active" in update_data
        ):
            raise BadRequestException(CANNOT_MODIFY_OWN_ROLE_OR_STATUS)

        target_user = await self.repository.get(target_user_id)
        if not target_user:
            raise NotFoundException(USER_NOT_FOUND.format(user_id=target_user_id))

        demoting_admin = (
            target_user.role == UserRole.ADMIN
            and target_user.is_active
            and (
                update_data.get("role") == UserRole.MEMBER
                or update_data.get("is_active") is False
            )
        )
        if demoting_admin:
            active_admins = await self.repository.count_active_admins()
            if active_admins <= 1:
                raise BadRequestException(LAST_ACTIVE_ADMIN_REQUIRED)

        updated = await self.repository.update(target_user, update_data)
        if update_data.get("is_active") is False:
            await self.repository.revoke_all_user_tokens(target_user.id)
        return UserResponse.model_validate(updated)

    async def delete_user_by_admin(
        self,
        target_user_id: int,
        current_admin: User,
    ) -> None:
        if current_admin.id == target_user_id:
            raise BadRequestException(CANNOT_DELETE_SELF)

        target_user = await self.repository.get(target_user_id)
        if not target_user:
            raise NotFoundException(USER_NOT_FOUND.format(user_id=target_user_id))

        if target_user.role == UserRole.ADMIN and target_user.is_active:
            active_admins = await self.repository.count_active_admins()
            if active_admins <= 1:
                raise BadRequestException(LAST_ACTIVE_ADMIN_REQUIRED)

        await self.repository.delete(target_user)

    async def _issue_tokens(self, user_id: int) -> TokenResponse:
        access_token = create_access_token(user_id)
        refresh_token, jti, expires_at = create_refresh_token(user_id)
        await self.repository.create_refresh_token(
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )


def get_auth_service(
    repository: Annotated[UserRepository, Depends(get_user_repository)],
) -> AuthService:
    return AuthService(repository=repository)
