from typing import Annotated
from fastapi import APIRouter, Depends, status

from app.dependencies import AdminUserDep, CurrentUserDep
from app.schemas.auth import UserMeUpdate, UserResponse, UserUpdate
from app.services.auth import AuthService, get_auth_service

router = APIRouter()

AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]

AUTH_RESPONSES = {
    status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
}
ADMIN_RESPONSES = {
    **AUTH_RESPONSES,
    status.HTTP_403_FORBIDDEN: {"description": "Forbidden"},
    status.HTTP_404_NOT_FOUND: {"description": "User not found"},
}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current authenticated user profile",
    responses={
        status.HTTP_200_OK: {"description": "Current user profile"},
        **AUTH_RESPONSES,
    },
)
async def get_me(current_user: CurrentUserDep) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Update current authenticated user profile",
    responses={
        status.HTTP_200_OK: {"description": "Profile updated successfully"},
        **AUTH_RESPONSES,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
    },
)
async def update_me(
    data: UserMeUpdate,
    current_user: CurrentUserDep,
    service: AuthServiceDep,
) -> UserResponse:
    return await service.update_me(current_user, data)


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update a user by ID (Admin only)",
    responses={
        status.HTTP_200_OK: {"description": "User updated successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Cannot demote or lock self/last admin"},
        **ADMIN_RESPONSES,
        status.HTTP_422_UNPROCESSABLE_ENTITY: {"description": "Validation error"},
    },
)
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_admin: AdminUserDep,
    service: AuthServiceDep,
) -> UserResponse:
    return await service.update_user_by_admin(user_id, data, current_admin)


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user by ID (Admin only)",
    responses={
        status.HTTP_204_NO_CONTENT: {"description": "User deleted successfully"},
        status.HTTP_400_BAD_REQUEST: {"description": "Cannot delete self or last admin"},
        **ADMIN_RESPONSES,
    },
)
async def delete_user(
    user_id: int,
    current_admin: AdminUserDep,
    service: AuthServiceDep,
) -> None:
    await service.delete_user_by_admin(user_id, current_admin)
