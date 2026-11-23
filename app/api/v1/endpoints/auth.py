from typing import Annotated
from fastapi import APIRouter, Depends, status

from app.dependencies import CurrentUserDep
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    UserUpdate,
)
from app.services.auth import AuthService, get_auth_service

router = APIRouter()
users_router = APIRouter()

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    data: RegisterRequest,
    service: AuthServiceDep,
) -> UserResponse:
    return await service.register(data)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate user and issue access & refresh tokens",
)
async def login(
    data: LoginRequest,
    service: AuthServiceDep,
) -> TokenResponse:
    return await service.login(data)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate refresh token and issue new token pair",
)
async def refresh_tokens(
    data: RefreshRequest,
    service: AuthServiceDep,
) -> TokenResponse:
    return await service.refresh_tokens(data.refresh_token)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change current user password and revoke old refresh tokens",
)
async def change_password(
    data: ChangePasswordRequest,
    current_user: CurrentUserDep,
    service: AuthServiceDep,
) -> None:
    await service.change_password(current_user, data)


@users_router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
)
async def get_me(current_user: CurrentUserDep) -> UserResponse:
    return UserResponse.model_validate(current_user)


@users_router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user by ID",
)
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: CurrentUserDep,
    service: AuthServiceDep,
) -> UserResponse:
    return await service.update_user(user_id, data, current_user)


@users_router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user by ID (Admin only)",
)
async def delete_user(
    user_id: int,
    current_user: CurrentUserDep,
    service: AuthServiceDep,
) -> None:
    await service.delete_user(user_id, current_user)
