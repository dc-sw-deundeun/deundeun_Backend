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
Auth/User, Onboarding, Record/OCR, HealthMetric, Character, Home, My(마이페이지), Notification, Search(질환 검색)는 구현되어 있습니다.
Analysis Stub MVP 라우트는 legacy 호환용으로 유지하지만 신규 프론트 화면에서는 호출하지 않습니다.
Mission API는 `GET /missions/today`, `POST /missions/{id}/complete`를 프론트 사용 구현 API로 제공합니다. 인증·캘린더·통계는 후속 Phase용 stub입니다.
PKG API는 미션 엔진/서버 내부 소비용입니다. 신규 프론트 화면에서는 직접 호출하지 않습니다.
Notification API는 알림함 목록·읽음 처리를 제공합니다. 알림 설정 화면은 `/my/notification-settings`를 사용하세요.

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

### Home / Character / Mission 흐름
- `GET /home`: 홈 화면용 사용자, 캐릭터 성장, 오늘 미션, 읽지 않은 알림 수를 한 번에 반환합니다.
- `GET /home/summary`: 홈 상단 위젯용 축약 수치를 반환합니다.
- `GET /characters/me`: 캐릭터 성장 상태와 실제 보유 동물 컬렉션을 반환합니다.
- `GET /characters/animals`: 전체 동물 카탈로그와 잠금/해금 상태를 반환합니다.
- `GET /missions/today`: 사용자 timezone 기준 오늘 배정된 미션 목록과 완료 집계를 반환합니다.
- `POST /missions/{id}/complete`: 본인 미션을 self-report로 완료 처리합니다. 캐릭터 EXP 지급은 후속 Phase입니다.

### 마이페이지 흐름
- `GET /my/connected-apps`: 연동 앱(APPLE_HEALTH, SAMSUNG_HEALTH, GOOGLE_FIT) 목록 및 상태 조회
- `PATCH /my/connected-apps/{provider}`: 연동 앱 상태 토글 (CONNECTED ↔ DISCONNECTED)
- `GET /my/notification-settings`: 알림 설정 조회 (없으면 기본값 true로 자동 생성)
- `PATCH /my/notification-settings`: 알림 설정 부분 업데이트 (변경할 항목만 전송)
- 비밀번호 변경: `POST /auth/password/reset/request` → `POST /auth/password/reset/confirm` 사용

### 질환 검색 흐름
- `GET /search/diseases?q=검색어`: 한국어 키워드로 질환 정보 조회
- 내부적으로 의학 지식 그래프(Neo4j)를 참조하여 AI가 한국어로 설명을 생성합니다.
- Neo4j 미연결 시에도 OpenAI만으로 결과를 반환합니다.

### PKG / Notification 구분
- `GET /pkg/{user_id}`: 서버/내부용 개인 지식그래프 조회입니다. 로그인 사용자는 본인 PKG만 조회할 수 있습니다.
- `GET /notifications`: 알림함 목록을 페이지네이션으로 조회합니다.
- `PATCH /notifications/{id}/read`: 알림을 읽음 처리합니다.
- 알림 설정 조회/수정은 마이페이지 API `GET/PATCH /my/notification-settings`를 사용합니다.

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
        "description": "[프론트 사용] 홈 화면 집계와 요약 API입니다. 알림 수는 Notification inbox의 미읽음 수를 반환합니다.",
    },
    {
        "name": "Mission",
        "description": "[프론트 사용] 오늘의 미션 조회와 self-report 완료 처리가 구현되어 있습니다. 인증·캘린더·통계 API는 후속 Phase stub입니다.",
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
        "name": "PKG",
        "description": (
            "[서버/내부] 개인 지식그래프 조회 API. "
            "미션 생성 엔진이 소비하는 조건·플래그·엣지 스냅샷을 반환합니다. "
            "신규 프론트 화면에서는 직접 호출하지 않습니다."
        ),
    },
    {
        "name": "Character",
        "description": "[프론트 사용] 캐릭터 성장 상태, 보유 동물 컬렉션, 동물 카탈로그 조회 API입니다.",
    },
    {
        "name": "My",
        "description": (
            "[프론트 사용] 마이페이지 API. "
            "연동 앱 관리(GET/PATCH /my/connected-apps), "
            "알림 설정(GET/PATCH /my/notification-settings) 구현 완료. "
            "프로필·앱잠금·문의·계정삭제는 후속 Phase stub(501)입니다."
        ),
    },
    {
        "name": "Notification",
        "description": (
            "[프론트 사용] 알림함 목록 조회와 읽음 처리 API입니다. "
            "알림 설정 화면은 My API의 GET/PATCH /my/notification-settings를 사용하세요."
        ),
    },
    {
        "name": "Search",
        "description": (
            "[프론트 사용] 질환 검색 API. "
            "GET /search/diseases?q=키워드 — 한국어 키워드로 질환명·설명·증상 목록을 반환합니다. "
            "의학 지식 그래프(Neo4j) + AI(OpenAI) 하이브리드 생성."
        ),
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
