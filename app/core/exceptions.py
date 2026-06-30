from collections.abc import Sequence
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
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


class UnprocessableEntityException(AppException):
    def __init__(
        self,
        message: str = "처리할 수 없는 요청입니다.",
        error_code: str = "UNPROCESSABLE_ENTITY",
    ) -> None:
        super().__init__(status_code=422, message=message, error_code=error_code)


class UnsupportedMediaTypeException(AppException):
    def __init__(
        self,
        message: str = "지원하지 않는 파일 형식입니다.",
        error_code: str = "UNSUPPORTED_MEDIA_TYPE",
    ) -> None:
        super().__init__(status_code=415, message=message, error_code=error_code)


class PayloadTooLargeException(AppException):
    def __init__(
        self,
        message: str = "업로드 가능한 파일 크기를 초과했습니다.",
        error_code: str = "PAYLOAD_TOO_LARGE",
    ) -> None:
        super().__init__(status_code=413, message=message, error_code=error_code)


class OcrFailedException(AppException):
    def __init__(
        self,
        message: str = "OCR 처리에 실패했습니다. 다시 시도해 주세요.",
        error_code: str = "OCR_FAILED",
    ) -> None:
        super().__init__(status_code=502, message=message, error_code=error_code)


class OcrBusyException(AppException):
    def __init__(
        self,
        retry_after_seconds: int,
        message: str = "OCR 요청이 많아 잠시 후 다시 시도해 주세요.",
        error_code: str = "OCR_BUSY",
    ) -> None:
        super().__init__(status_code=429, message=message, error_code=error_code)
        self.retry_after_seconds = retry_after_seconds


class InvalidImageCountException(AppException):
    def __init__(
        self,
        message: str = "이미지는 1장 이상 10장 이하로 업로드해 주세요.",
        error_code: str = "INVALID_IMAGE_COUNT",
    ) -> None:
        super().__init__(status_code=400, message=message, error_code=error_code)


def _sanitize_validation_errors(errors: Sequence[Any]) -> list[Any]:
    sanitized: list[Any] = []
    for error in errors:
        if not isinstance(error, dict):
            sanitized.append(error)
            continue
        item = dict(error)
        ctx = item.get("ctx")
        if isinstance(ctx, dict):
            item["ctx"] = {
                key: str(value) if isinstance(value, Exception) else value
                for key, value in ctx.items()
            }
        sanitized.append(item)
    return sanitized


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        for error in exc.errors():
            if error.get("type") in {"too_long", "too_short"} and tuple(error.get("loc", ())) == (
                "body",
                "images",
            ):
                invalid_count = InvalidImageCountException()
                return JSONResponse(
                    status_code=invalid_count.status_code,
                    content={
                        "success": False,
                        "message": invalid_count.message,
                        "data": None,
                        "error_code": invalid_count.error_code,
                    },
                )
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder(
                {
                    "success": False,
                    "message": "입력값이 올바르지 않습니다.",
                    "data": {"detail": _sanitize_validation_errors(exc.errors())},
                    "error_code": "VALIDATION_ERROR",
                }
            ),
        )

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        data = None
        headers = None
        retry_after_seconds = getattr(exc, "retry_after_seconds", None)
        if retry_after_seconds is not None:
            data = {"retry_after_seconds": retry_after_seconds}
            headers = {"Retry-After": str(retry_after_seconds)}
        return JSONResponse(
            status_code=exc.status_code,
            headers=headers,
            content={
                "success": False,
                "message": exc.message,
                "data": data,
                "error_code": exc.error_code,
            },
        )
