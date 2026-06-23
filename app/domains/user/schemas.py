from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class CurrentUser(BaseModel):
    """get_current_user 의존성이 반환하는 인증된 사용자 정보."""

    id: int


class UserSummaryResponse(BaseModel):
    """로그인·회원가입 응답에 포함되는 사용자 요약."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nickname: str
    onboarding_step: str


class MeResponse(BaseModel):
    """GET /auth/me 전체 프로필."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    nickname: str
    onboarding_step: str
    timezone: str
    status: str
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    nickname: str | None = None
