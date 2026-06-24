from pydantic import BaseModel, EmailStr, Field, field_validator

from app.domains.auth.models import VerificationPurpose
from app.domains.auth.validators import validate_password_policy
from app.domains.user.schemas import UserSummaryResponse


class EmailVerifyRequest(BaseModel):
    email: EmailStr
    purpose: VerificationPurpose = VerificationPurpose.SIGNUP


class EmailVerifyConfirmRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    purpose: VerificationPurpose = VerificationPurpose.SIGNUP


class EmailVerifyConfirmResponse(BaseModel):
    verification_token: str


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    nickname: str = Field(min_length=1, max_length=50)
    verification_token: str

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        return validate_password_policy(value)


class SignupResponse(BaseModel):
    user: UserSummaryResponse


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"
    user: UserSummaryResponse


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        return validate_password_policy(value)
