from pydantic import BaseModel


class SignupRequest(BaseModel):
    # email: str
    # password: str
    # nickname: str
    pass


class SignupResponse(BaseModel):
    # user_id: int
    # email: str
    # nickname: str
    pass


class LoginRequest(BaseModel):
    # email: str
    # password: str
    pass


class LoginResponse(BaseModel):
    # access_token: str
    # refresh_token: str
    # token_type: str
    pass


class TokenRefreshRequest(BaseModel):
    # refresh_token: str
    pass


class EmailVerifyRequest(BaseModel):
    # email: str
    pass


class EmailVerifyConfirmRequest(BaseModel):
    # token: str
    pass


class PasswordResetRequest(BaseModel):
    # email: str
    pass


class PasswordResetConfirmRequest(BaseModel):
    # token: str
    # new_password: str
    pass
