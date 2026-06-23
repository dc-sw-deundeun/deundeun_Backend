from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class AppException(Exception):
    def __init__(self, status_code: int, message: str, error_code: str) -> None:
        self.status_code = status_code
        self.message = message
        self.error_code = error_code


class AuthException(AppException):
    def __init__(
        self, message: str = "인증이 필요합니다.", error_code: str = "AUTH_REQUIRED"
    ) -> None:
        super().__init__(status_code=401, message=message, error_code=error_code)


class ForbiddenException(AppException):
    def __init__(self, message: str = "권한이 없습니다.", error_code: str = "FORBIDDEN") -> None:
        super().__init__(status_code=403, message=message, error_code=error_code)


class NotFoundException(AppException):
    def __init__(
        self, message: str = "데이터를 찾을 수 없습니다.", error_code: str = "NOT_FOUND"
    ) -> None:
        super().__init__(status_code=404, message=message, error_code=error_code)


class ConflictException(AppException):
    def __init__(self, message: str = "이미 존재합니다.", error_code: str = "CONFLICT") -> None:
        super().__init__(status_code=409, message=message, error_code=error_code)


class BadRequestException(AppException):
    def __init__(
        self, message: str = "잘못된 요청입니다.", error_code: str = "BAD_REQUEST"
    ) -> None:
        super().__init__(status_code=400, message=message, error_code=error_code)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        data = None
        retry_after_seconds = getattr(exc, "retry_after_seconds", None)
        if retry_after_seconds is not None:
            data = {"retry_after_seconds": retry_after_seconds}
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": exc.message,
                "data": data,
                "error_code": exc.error_code,
            },
        )
