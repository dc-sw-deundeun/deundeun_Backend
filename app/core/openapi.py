"""OpenAPI(Swagger) 메타데이터 및 보안 스키마 설정."""

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

_API_DESCRIPTION = """
## 든든 건강미션 앱 백엔드 API

공통 응답 형식: `ApiResponse { success, message, data, error_code }`

### Swagger 표기 기준
- `[프론트 사용]`: 현재 프론트엔드가 연동해도 되는 구현 API입니다.
- `[호환]`: 기존 클라이언트 호환용 alias입니다. 신규 화면은 설명에 적힌 권장 API를 사용하세요.
- `[서버/내부]`: 프론트 화면에서 직접 호출하지 않는 운영·콜백·상태 확인 API입니다.
- `[프론트 작업 제외]`: 라우트는 열려 있지만 아직 stub이거나 후속 Phase용입니다. 호출 시 `NOT_IMPLEMENTED`(501)를 기대해야 합니다.

### 현재 프론트 연동 가능 영역
Auth/User, Onboarding, Record/OCR, HealthMetric은 구현되어 있습니다.
Home, Mission, Character, Notification, My는 후속 Phase용 stub입니다.
Analysis Stub MVP 라우트는 legacy 호환용으로 유지하지만 신규 프론트 화면에서는 호출하지 않습니다.
Mission API는 아직 stub이며, "오늘의 미션으로 받기" HTTP API는 후속 Phase에서 구현합니다.

### 인증 흐름
1. `POST /auth/email/verify/request` — 인증 코드 발송
2. `POST /auth/email/verify/confirm` — 코드 확인 → `verification_token` 발급
3. `POST /auth/signup` — 회원가입
4. `POST /auth/login` — `access_token` + `refresh_token` 발급
5. 우측 **Authorize**에 `access_token` 입력 후 보호 API 호출

> SMTP 미설정 시 StubEmailClient가 동작하며, 인증 코드는 서버 로그에 출력됩니다.

### 검진/OCR 권장 흐름
1. `POST /records/checkups/ocr-preview` — 이미지 base64 배열 업로드, OCR preview 확인
2. `POST /records/checkups` — 사용자가 확인·수정한 preview 결과를 검진 기록으로 저장
3. `POST /records/checkups/{record_id}/verify` — 검진 검수 완료 및 온보딩 단계 전환
4. `POST /health-metrics/analyses` — 프론트가 확정한 metric 배열로 HealthMetric 분석 저장
5. `GET /health-metrics/analyses/{analysis_id}` — 저장 분석 재조회

### HealthMetric 분석 흐름
- `POST /health-metrics/analyses`: 인증 필요. `sex`, `measured_at`, `metrics[]`를 받아 분석을 저장합니다.
- 생성 응답은 `data: null`입니다. 분석 결과는 GET `/health-metrics/analyses/{analysis_id}`로 조회합니다.
- GET 응답은 `analysis_id`, `record_id`, `results`, `explanation`, `ui.summary`, `ui.details`를 포함합니다. `ui.details[].trend.points`에는 이전 HealthMetric 분석 이력이 포함됩니다.

### Legacy Analysis Stub
`/api/v1/analysis/*`는 Phase 4 Stub MVP 호환용입니다. 신규 프론트 화면은 `/health-metrics/*`를 사용하세요.
"""

_OPENAPI_TAGS = [
    {
        "name": "Health",
        "description": "[서버/내부] 서버 상태 확인. 프론트 화면 구현 대상이 아닙니다.",
    },
    {
        "name": "Auth",
        "description": "[프론트 사용] 회원가입·로그인·토큰·이메일 인증·비밀번호 재설정.",
    },
    {
        "name": "Onboarding",
        "description": "[프론트 사용] 온보딩 상태·웨어러블 연결·완료 처리. 초기 검진 업로드는 Record API를 사용합니다.",
    },
    {
        "name": "Home",
        "description": "[프론트 작업 제외] 홈 집계 API는 후속 Phase stub입니다.",
    },
    {
        "name": "Mission",
        "description": "[프론트 작업 제외] 미션 API는 Phase 5 예정 stub입니다. HealthMetric 기반 미션 생성 API는 후속 구현 대상입니다.",
    },
    {
        "name": "Record",
        "description": "[프론트 사용] 검진 이미지 OCR preview, 검진 기록 저장·조회·수정·검수. OCR 전용 라우터는 제거되었고 Record API로 통합되었습니다.",
    },
    {
        "name": "HealthMetric",
        "description": "[프론트 사용] 건강검진 항목 평가, 분석 저장, 저장 분석 조회. 실제 검진 분석 결과의 정본입니다.",
    },
    {
        "name": "Analysis",
        "description": "[프론트 작업 제외] Legacy Phase 4 Stub API입니다. 신규 화면은 HealthMetric 분석 API를 사용하세요. callback은 서버/내부용입니다.",
    },
    {
        "name": "Character",
        "description": "[프론트 작업 제외] 캐릭터·성장 API는 후속 Phase stub입니다.",
    },
    {
        "name": "My",
        "description": "[프론트 작업 제외] 마이페이지 API는 후속 Phase stub입니다.",
    },
    {
        "name": "Notification",
        "description": "[프론트 작업 제외] 알림 API는 후속 Phase stub입니다.",
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
