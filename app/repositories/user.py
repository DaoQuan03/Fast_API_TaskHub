from datetime import datetime
from typing import Annotated
from fastapi import Depends
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ConflictException
from app.core.messages import EMAIL_ALREADY_EXISTS
from app.models.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email)
        return await self.session.scalar(stmt)

    async def create_user(
        self,
        *,
        email: str,
        full_name: str,
        hashed_password: str,
        role: UserRole = UserRole.MEMBER,
    ) -> User:
        try:
            return await self.create(
                email=email,
                full_name=full_name,
                hashed_password=hashed_password,
                role=role,
            )
        except IntegrityError:
            await self.session.rollback()
            raise ConflictException(EMAIL_ALREADY_EXISTS)

    async def count_active_admins(self) -> int:
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        )
        count = await self.session.scalar(stmt)
        return count or 0

    async def create_refresh_token(
        self,
        *,
        jti: str,
        user_id: int,
        expires_at: datetime,
    ) -> RefreshToken:
        token = RefreshToken(
            jti=jti,
            user_id=user_id,
            expires_at=expires_at,
            revoked=False,
        )
        self.session.add(token)
        await self.session.flush()
        return token

    async def get_refresh_token_by_jti(self, jti: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.jti == jti)
        return await self.session.scalar(stmt)

    async def atomic_revoke_refresh_token(self, jti: str) -> bool:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.jti == jti, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()
        return (result.rowcount or 0) > 0

    async def revoke_all_user_tokens(self, user_id: int) -> None:
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        await self.session.execute(stmt)
        await self.session.flush()


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserRepository:
    return UserRepository(session=session)
