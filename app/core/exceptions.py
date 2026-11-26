from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)


class BadRequestException(AppException):
    status_code: int = status.HTTP_400_BAD_REQUEST


class UnauthorizedException(AppException):
    status_code: int = status.HTTP_401_UNAUTHORIZED


class ForbiddenException(AppException):
    status_code: int = status.HTTP_403_FORBIDDEN


class NotFoundException(AppException):
    status_code: int = status.HTTP_404_NOT_FOUND


class ConflictException(AppException):
    status_code: int = status.HTTP_409_CONFLICT


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    headers = (
        {"WWW-Authenticate": "Bearer"}
        if exc.status_code == status.HTTP_401_UNAUTHORIZED
        else None
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
        headers=headers,
    )
