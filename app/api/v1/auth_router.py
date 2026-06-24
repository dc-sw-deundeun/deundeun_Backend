from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials

from app.core.dependencies import (
    bearer_scheme,
    get_auth_service,
    get_current_user,
    get_current_user_model,
)
from app.core.response import not_implemented_response, success_response
from app.domains.auth.schemas import (
    EmailVerifyConfirmRequest,
    EmailVerifyRequest,
    LoginRequest,
    LogoutRequest,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    SignupRequest,
    TokenRefreshRequest,
)
from app.domains.auth.service import AuthService
from app.domains.user.models import User
from app.domains.user.schemas import CurrentUser, MeResponse

router = APIRouter()


@router.post(
    "/email/verify/request",
    summary="이메일 인증 코드 발송",
    description="6자리 인증 코드를 이메일로 발송합니다. SMTP 미설정 시 서버 로그에 코드가 출력됩니다.",
)
async def request_email_verification(
    body: EmailVerifyRequest,
    service: AuthService = Depends(get_auth_service),
):
    await service.request_email_verification(body.email, body.purpose)
    return success_response(message="인증 코드를 발송했습니다.")


@router.post(
    "/email/verify/confirm",
    summary="이메일 인증 코드 확인",
    description="인증 성공 시 signup에 사용할 `verification_token`을 반환합니다.",
)
def confirm_email_verification(
    body: EmailVerifyConfirmRequest,
    service: AuthService = Depends(get_auth_service),
):
    result = service.confirm_email_verification(body.email, body.code, body.purpose)
    return success_response(message="이메일 인증이 완료되었습니다.", data=result.model_dump())


@router.post("/signup", summary="회원가입", description="이메일 인증 완료 후 계정을 생성합니다.")
def signup(
    body: SignupRequest,
    service: AuthService = Depends(get_auth_service),
):
    user = service.signup(body)
    return success_response(message="회원가입이 완료되었습니다.", data={"user": user.model_dump()})


@router.post(
    "/login",
    summary="로그인",
    description="access_token과 refresh_token을 발급합니다. Swagger 테스트 시 access_token을 Authorize에 등록하세요.",
)
def login(
    body: LoginRequest,
    service: AuthService = Depends(get_auth_service),
):
    result = service.login(body)
    return success_response(message="로그인되었습니다.", data=result.model_dump())


@router.post(
    "/refresh",
    summary="토큰 재발급",
    description="refresh_token으로 새 access·refresh token을 발급합니다.",
)
def refresh_token(
    body: TokenRefreshRequest,
    service: AuthService = Depends(get_auth_service),
):
    result = service.refresh_token(body.refresh_token)
    return success_response(message="토큰이 재발급되었습니다.", data=result.model_dump())


@router.post(
    "/logout",
    summary="로그아웃",
    description="현재 access token을 블랙리스트에 등록하고 refresh token을 폐기합니다. Authorization 헤더 필요.",
    dependencies=[Security(bearer_scheme)],
)
def logout(
    body: LogoutRequest,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    current_user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
):
    access_token = credentials.credentials if credentials else ""
    service.logout(access_token=access_token, refresh_token=body.refresh_token)
    return success_response(message="로그아웃되었습니다.")


@router.post("/password/reset/request", summary="비밀번호 재설정 코드 발송")
async def request_password_reset(
    body: PasswordResetRequest,
    service: AuthService = Depends(get_auth_service),
):
    await service.request_password_reset(body.email)
    return success_response(message="비밀번호 재설정 코드를 발송했습니다.")


@router.post(
    "/password/reset/confirm",
    summary="비밀번호 재설정 완료",
    description="재설정 후 모든 refresh·access token이 무효화됩니다.",
)
def confirm_password_reset(
    body: PasswordResetConfirmRequest,
    service: AuthService = Depends(get_auth_service),
):
    service.confirm_password_reset(body.email, body.code, body.new_password)
    return success_response(message="비밀번호가 재설정되었습니다.")


@router.post("/policies/agree")
async def agree_policies():
    return not_implemented_response()


@router.get(
    "/me",
    summary="내 프로필 조회",
    description="인증된 사용자의 프로필을 반환합니다. Authorization 헤더 필요.",
    dependencies=[Security(bearer_scheme)],
)
def get_me(
    user: User = Depends(get_current_user_model),
):
    return success_response(data=MeResponse.model_validate(user).model_dump(mode="json"))
