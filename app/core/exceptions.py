from fastapi import Request, status
from fastapi.responses import JSONResponse

class AppException(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.message)

class NotFoundException(AppException):
    status_code: int = status.HTTP_404_NOT_FOUND

async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    return JSONResponse(
        status_code = exc.status_code,
        content={"detail": exc.message},
    )