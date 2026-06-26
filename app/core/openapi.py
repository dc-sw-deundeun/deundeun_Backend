"""OpenAPI(Swagger) 메타데이터 및 보안 스키마 설정."""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

_API_DESCRIPTION = """
## 든든 건강미션 앱 백엔드 API

공통 응답 형식: `ApiResponse { success, message, data, error_code }`

### 인증 (Phase 1)
1. `POST /auth/email/verify/request` — 인증 코드 발송
2. `POST /auth/email/verify/confirm` — 코드 확인 → `verification_token` 발급
3. `POST /auth/signup` — 회원가입
4. `POST /auth/login` — `access_token` + `refresh_token` 발급
5. 우측 **Authorize**에 `access_token` 입력 후 보호 API 호출

> SMTP 미설정 시 StubEmailClient가 동작하며, 인증 코드는 서버 로그에 출력됩니다.
"""

_OPENAPI_TAGS = [
    {
        "name": "Health",
        "description": "서버 상태 확인",
    },
    {
        "name": "Auth",
        "description": "회원가입·로그인·토큰·이메일 인증·비밀번호 재설정 (Phase 1)",
    },
    {
        "name": "Onboarding",
        "description": "온보딩·약관·웨어러블 (Phase 2, iOS Apple Health / Android Health Connect)",
    },
    {
        "name": "Home",
        "description": "홈 집계 API (Phase 6 예정)",
    },
    {
        "name": "Mission",
        "description": "미션 API (Phase 5 예정)",
    },
    {
        "name": "Record",
        "description": "검진 기록 API (Phase 3 예정)",
    },
    {
        "name": "Analysis",
        "description": "외부 AI 분석 API (Phase 4 예정)",
    },
    {
        "name": "Character",
        "description": "캐릭터·성장 API (Phase 5 예정)",
    },
    {
        "name": "My",
        "description": "마이페이지 API (Phase 8 예정)",
    },
    {
        "name": "Notification",
        "description": "알림 API (Phase 7 예정)",
    },
]


def configure_openapi(app: FastAPI) -> None:
    """Swagger UI / ReDoc용 OpenAPI 스키마를 커스터마이즈한다."""

    def custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=_API_DESCRIPTION,
            routes=app.routes,
            tags=_OPENAPI_TAGS,
        )

        schema.setdefault("components", {}).setdefault("securitySchemes", {})["BearerAuth"] = {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "로그인(`POST /api/v1/auth/login`) 응답의 `access_token`을 입력하세요. "
                "형식: Bearer 없이 토큰 문자열만 붙여넣기"
            ),
        }

        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
