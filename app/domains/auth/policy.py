"""인증 도메인 정책 상수.

이메일 인증 코드·로그인 잠금 등 비즈니스 규칙 수치를 한 곳에서 관리한다.
SMTP 메일 템플릿(`smtp_email_client.py`)의 "10분 후 만료" 문구와 일치시킨다.
"""

from app.domains.auth.models import ConsentType

VERIFICATION_CODE_LENGTH = 6
VERIFICATION_CODE_EXPIRE_MINUTES = 10
VERIFICATION_MAX_ATTEMPTS = 5
VERIFICATION_RESEND_COOLDOWN_SECONDS = 60

VERIFICATION_TOKEN_EXPIRE_MINUTES = 30

LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_MINUTES = 15

# 온보딩 약관 동의 (Phase 2)
# 가입 후 반드시 동의해야 진행 가능한 필수 약관 목록.
REQUIRED_CONSENT_TYPES: tuple[ConsentType, ...] = (
    ConsentType.TERMS_OF_SERVICE,
    ConsentType.PRIVACY,
    ConsentType.HEALTH_DATA,
)

# 각 약관의 현재 유효 버전. 약관 개정 시 이 값을 올리면
# 구버전 동의는 POLICY_VERSION_MISMATCH로 거부된다.
CURRENT_POLICY_VERSIONS: dict[ConsentType, str] = {
    ConsentType.TERMS_OF_SERVICE: "1.0",
    ConsentType.PRIVACY: "1.0",
    ConsentType.HEALTH_DATA: "1.0",
}
