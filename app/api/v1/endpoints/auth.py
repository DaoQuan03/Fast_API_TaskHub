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
)
from app.services.auth import AuthService, get_auth_service

router = APIRouter()

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

UNAUTHORIZED_RESPONSE = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
}
VALIDATION_RESPONSE = {
    status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
}


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    responses={
        status.HTTP_201_CREATED: {"description": "User registered successfully"},
        status.HTTP_409_CONFLICT: {"description": "Email already exists"},
        **VALIDATION_RESPONSE,
    },
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
    responses={
        status.HTTP_200_OK: {"description": "Authenticated successfully"},
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_RESPONSE,
    },
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
    responses={
        status.HTTP_200_OK: {"description": "Tokens refreshed successfully"},
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_RESPONSE,
    },
)
async def refresh_tokens(
    data: RefreshRequest,
    service: AuthServiceDep,
) -> TokenResponse:
    return await service.refresh_tokens(data.refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke refresh token and log out",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Logged out successfully"},
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_RESPONSE,
    },
)
async def logout(
    data: RefreshRequest,
    service: AuthServiceDep,
) -> None:
    await service.logout(data.refresh_token)


@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change current user password and revoke old tokens",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "Password changed successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Incorrect current password"},
        **UNAUTHORIZED_RESPONSE,
        **VALIDATION_RESPONSE,
    },
)
async def change_password(
    data: ChangePasswordRequest,
    current_user: CurrentUserDep,
    service: AuthServiceDep,
) -> None:
    await service.change_password(current_user, data)
