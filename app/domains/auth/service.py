import secrets
from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.core.exceptions import ForbiddenException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_verification_token,
    decode_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.domains.auth import policy
from app.domains.auth.exceptions import (
    AccountLockedException,
    ConsentRequiredException,
    EmailAlreadyExistsException,
    InvalidCredentialsException,
    InvalidTokenException,
    InvalidVerificationCodeException,
    NotVerifiedException,
    PolicyVersionMismatchException,
    ResendTooSoonException,
    SamePasswordException,
    VerificationAttemptsExceededException,
    VerificationCodeExpiredException,
)
from app.domains.auth.models import EmailVerification, RefreshToken, VerificationPurpose
from app.domains.auth.repository import AuthRepository
from app.domains.auth.schemas import (
    AccessTokenResponse,
    EmailVerifyConfirmResponse,
    LoginRequest,
    PoliciesAgreeRequest,
    PoliciesAgreeResponse,
    SignupRequest,
    TokenResponse,
)
from app.domains.onboarding import policy as onboarding_policy
from app.domains.user.models import OnboardingStep, User, UserStatus
from app.domains.user.schemas import UserSummaryResponse
from app.infrastructure.email.email_client import EmailClient


class AuthService:
    def __init__(self, repo: AuthRepository, email_client: EmailClient) -> None:
        self.repo = repo
        self.email_client = email_client

    # --- 이메일 인증 ---
    async def request_email_verification(self, email: str, purpose: VerificationPurpose) -> None:
        if purpose == VerificationPurpose.SIGNUP:
            if self.repo.find_user_by_email(email) is not None:
                raise EmailAlreadyExistsException()
        elif self.repo.find_user_by_email(email) is None:
            # 비밀번호 재설정: 미가입 이메일도 성공 응답 (이메일 열거 방지)
            return

        self._check_resend_cooldown(email, purpose)

        code = self._generate_code()
        now = datetime.now(UTC)
        verification = EmailVerification(
            email=email,
            purpose=purpose,
            code_hash=hash_password(code),
            expires_at=now + timedelta(minutes=policy.VERIFICATION_CODE_EXPIRE_MINUTES),
        )
        self.repo.create_email_verification(verification)

        # 메일 발송이 실패하면 인증 레코드(쿨다운 상태)를 남기지 않는다.
        try:
            if purpose == VerificationPurpose.SIGNUP:
                await self.email_client.send_verification_email(to=email, code=code)
            else:
                await self.email_client.send_password_reset_email(to=email, code=code)
        except Exception:
            self.repo.db.rollback()
            raise

        self.repo.db.commit()

    def confirm_email_verification(
        self, email: str, code: str, purpose: VerificationPurpose
    ) -> EmailVerifyConfirmResponse:
        self._verify_code(email, purpose, code)
        token = create_verification_token(
            email=email,
            purpose=purpose.value,
            expires_delta=timedelta(minutes=policy.VERIFICATION_TOKEN_EXPIRE_MINUTES),
        )
        return EmailVerifyConfirmResponse(verification_token=token)

    # --- 회원가입 ---
    def signup(self, request: SignupRequest) -> UserSummaryResponse:
        payload = decode_token(request.verification_token)
        if (
            payload.get("type") != "email_verification"
            or payload.get("purpose") != VerificationPurpose.SIGNUP.value
            or payload.get("sub") != request.email
        ):
            raise InvalidTokenException()

        verification = self.repo.find_verified_verification(
            request.email, VerificationPurpose.SIGNUP
        )
        if verification is None:
            raise NotVerifiedException()

        if self.repo.find_user_by_email(request.email) is not None:
            raise EmailAlreadyExistsException()

        user = User(
            email=request.email,
            password_hash=hash_password(request.password),
            nickname=request.nickname,
        )
        self.repo.save_user(user)
        self.repo.db.commit()
        self.repo.db.refresh(user)
        return UserSummaryResponse.model_validate(user)

    # --- 로그인 ---
    def login(self, request: LoginRequest) -> TokenResponse:
        user = self.repo.find_user_by_email(request.email)
        if user is None:
            raise InvalidCredentialsException()

        now = datetime.now(UTC)
        if user.locked_until is not None and user.locked_until > now:
            raise AccountLockedException(
                retry_after_seconds=int((user.locked_until - now).total_seconds())
            )

        # 잠금이 만료된 경우 실패 카운터를 초기화한 뒤 새 시도를 집계한다 (즉시 재잠금 방지).
        if user.locked_until is not None:
            self.repo.reset_failed_login(user)

        if not verify_password(request.password, user.password_hash):
            self.repo.increment_failed_login(user)
            if user.failed_login_count >= policy.LOGIN_MAX_FAILURES:
                self.repo.set_locked_until(
                    user, now + timedelta(minutes=policy.LOGIN_LOCKOUT_MINUTES)
                )
            self.repo.db.commit()
            raise InvalidCredentialsException()

        if user.status != UserStatus.ACTIVE:
            raise ForbiddenException(
                message="사용할 수 없는 계정입니다.", error_code="ACCOUNT_INACTIVE"
            )

        self.repo.reset_failed_login(user)
        tokens = self._issue_tokens(user)
        self.repo.db.commit()

        return TokenResponse(
            access_token=tokens[0],
            refresh_token=tokens[1],
            expires_in=settings.jwt_access_token_expire_minutes * 60,
            user=UserSummaryResponse.model_validate(user),
        )

    # --- 토큰 ---
    def refresh_token(self, refresh_token: str) -> AccessTokenResponse:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise InvalidTokenException()

        stored = self.repo.find_refresh_token_by_hash(hash_token(refresh_token))
        now = datetime.now(UTC)
        if stored is None or stored.revoked_at is not None or stored.expires_at < now:
            raise InvalidTokenException()

        user = self.repo.get_user_by_id(stored.user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidTokenException()

        self.repo.revoke_refresh_token(stored, now)
        access, new_refresh = self._issue_tokens(user)
        self.repo.db.commit()

        return AccessTokenResponse(
            access_token=access,
            refresh_token=new_refresh,
            expires_in=settings.jwt_access_token_expire_minutes * 60,
        )

    def logout(self, access_token: str, refresh_token: str | None) -> None:
        payload = decode_token(access_token)
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            self.repo.blacklist_access_token(
                jti=jti, expires_at=datetime.fromtimestamp(exp, tz=UTC)
            )

        if refresh_token:
            stored = self.repo.find_refresh_token_by_hash(hash_token(refresh_token))
            if stored is not None and stored.revoked_at is None:
                self.repo.revoke_refresh_token(stored, datetime.now(UTC))

        self.repo.db.commit()

    # --- 비밀번호 재설정 ---
    async def request_password_reset(self, email: str) -> None:
        await self.request_email_verification(email, VerificationPurpose.PASSWORD_RESET)

    def confirm_password_reset(self, email: str, code: str, new_password: str) -> None:
        self._verify_code(email, VerificationPurpose.PASSWORD_RESET, code)

        user = self.repo.find_user_by_email(email)
        if user is None:
            raise InvalidCredentialsException()
        if verify_password(new_password, user.password_hash):
            raise SamePasswordException()

        user.password_hash = hash_password(new_password)
        now = datetime.now(UTC)
        self.repo.revoke_all_user_refresh_tokens(user.id, now)
        self.repo.increment_token_version(user)
        self.repo.db.commit()

    # --- 온보딩 약관 동의 ---
    def agree_policies(self, user_id: int, request: PoliciesAgreeRequest) -> PoliciesAgreeResponse:
        user = self.repo.get_user_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidTokenException()

        onboarding_policy.ensure_step(user.onboarding_step, OnboardingStep.CONSENT)

        consent_types = [item.consent_type for item in request.consents]
        required_types = set(policy.REQUIRED_CONSENT_TYPES)
        allowed_types = set(policy.ALLOWED_CONSENT_TYPES)
        if len(consent_types) != len(set(consent_types)) or not set(consent_types).issubset(
            allowed_types
        ):
            raise ConsentRequiredException()

        provided = {item.consent_type: item for item in request.consents}
        for required in policy.REQUIRED_CONSENT_TYPES:
            item = provided.get(required)
            if item is None or not item.agreed:
                raise ConsentRequiredException()
            if item.version != policy.CURRENT_POLICY_VERSIONS[required]:
                raise PolicyVersionMismatchException()

        for item in request.consents:
            if item.version != policy.CURRENT_POLICY_VERSIONS[item.consent_type]:
                raise PolicyVersionMismatchException()
            if item.consent_type in required_types and not item.agreed:
                raise ConsentRequiredException()
            self.repo.add_consent_history(
                user_id=user.id,
                consent_type=item.consent_type.value,
                version=item.version,
                agreed=item.agreed,
            )

        user.onboarding_step = OnboardingStep.WEARABLE
        self.repo.db.commit()
        return PoliciesAgreeResponse(onboarding_step=OnboardingStep.WEARABLE.value)

    # --- 내부 헬퍼 ---
    def _generate_code(self) -> str:
        upper = 10**policy.VERIFICATION_CODE_LENGTH
        return f"{secrets.randbelow(upper):0{policy.VERIFICATION_CODE_LENGTH}d}"

    def _check_resend_cooldown(self, email: str, purpose: VerificationPurpose) -> None:
        latest = self.repo.find_latest_verification(email, purpose)
        if latest is None:
            return
        elapsed = (datetime.now(UTC) - latest.created_at).total_seconds()
        remaining = policy.VERIFICATION_RESEND_COOLDOWN_SECONDS - elapsed
        if remaining > 0:
            raise ResendTooSoonException(retry_after_seconds=int(remaining) + 1)

    def _verify_code(
        self, email: str, purpose: VerificationPurpose, code: str
    ) -> EmailVerification:
        verification = self.repo.find_latest_unverified_verification(email, purpose)
        now = datetime.now(UTC)
        if verification is None:
            raise InvalidVerificationCodeException()
        if verification.expires_at < now:
            raise VerificationCodeExpiredException()
        if verification.attempt_count >= policy.VERIFICATION_MAX_ATTEMPTS:
            raise VerificationAttemptsExceededException()
        if not verify_password(code, verification.code_hash):
            verification.attempt_count += 1
            self.repo.db.commit()
            raise InvalidVerificationCodeException()
        verification.verified_at = now
        self.repo.db.commit()
        return verification

    def _issue_tokens(self, user: User) -> tuple[str, str]:
        access = create_access_token(subject=user.id, token_version=user.token_version)
        refresh = create_refresh_token(subject=user.id)
        self.repo.save_refresh_token(
            RefreshToken(
                user_id=user.id,
                token_hash=hash_token(refresh),
                expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_expire_days),
            )
        )
        return access, refresh
