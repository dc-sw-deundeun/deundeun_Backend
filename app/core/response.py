from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None
    error_code: Optional[str] = None


def success_response(message: str = "요청이 성공했습니다.", data=None) -> dict:
    return ApiResponse(success=True, message=message, data=data).model_dump()


def error_response(message: str, error_code: str, data=None) -> dict:
    return ApiResponse(success=False, message=message, data=data, error_code=error_code).model_dump()
