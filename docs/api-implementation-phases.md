# deundeun Backend API 구현 Phase 계획

> 작성일: 2026-06-23  
> 최종 수정: 2026-06-26 (OCR 파이프라인 구현 반영 — D-BE-001 번복)  
> 기준 문서: [요구사항정의서](./든든_건강미션앱_요구사항정의서_개발설계서_v0.1%20.md), [architecture.md](./architecture.md)  
> 현재 상태: Phase 1(Auth) 완료, Phase 3 검진 기록 + **OCR 파이프라인** 구현 완료 ([implementation-status.md](./implementation-status.md))

> ⚠️ **현행화 안내 (2026-06-26)**: 본 문서는 초기 계획에서 **OCR을 범위 제외**(D-BE-001)했으나,
> 이후 PR #6에서 **Clova OCR 기반 검진표 자동 인식 파이프라인이 실제로 구현·머지**되었다.
> 따라서 §1.2의 "OCR 제외"는 더 이상 유효하지 않으며, 검진 등록 흐름은
> `업로드 → OCR 미리보기 → 커밋 → 검수`로 동작한다 ([§6](#6-phase-3--검진-기록-record--ocr)).
> 실제 구현 현황은 [implementation-status.md](./implementation-status.md)를 정본으로 삼는다.

---

## 1. 범위 정리

### 1.1 이번 백엔드에서 구현하는 것

| 영역 | 포함 |
|------|------|
| 인증·계정 | 이메일 인증, 회원가입, 로그인, 토큰, 비밀번호 재설정·변경 |
| 온보딩 | 약관 동의, 건강 앱 연동(건너뛰기), 온보딩 단계 추적 |
| 검진 기록 | 이미지 업로드·직접 입력, 수치 CRUD, 검수(verify), 목록·상세·추이 |
| 외부 AI 분석 | 분석 요청·상태·결과·callback (FastAPI는 추론 미수행) |
| 미션·성장 | 오늘의 미션, 완료·증빙, XP·레벨·연속 실천, 캐릭터 |
| 홈·알림·마이 | 홈 집계, 알림함·설정, 프로필·검색 |

### 1.2 OCR 파이프라인 (구현 완료, 2026-06-26)

> 초기 계획에서는 OCR을 범위 제외했으나, **PR #6에서 Clova OCR 기반 검진표 인식이 구현·머지**되었다.
> 아래 항목은 모두 **현재 코드에 존재**한다.

| 구현 항목 | 위치 |
|-----------|------|
| `domains/ocr/` (service·repository·dependencies·status) | Clova 결과 파싱·커밋·job 관리 |
| `infrastructure/ocr/` (clova_client·parser·metric_dictionary·format) | Clova 호출·규칙 파서·지표 사전 |
| `api/v1/ocr_router.py` | `GET /ocr/jobs/{job_id}` — OCR job 상태 조회 |
| `OcrJob` 테이블·모델 | 마이그레이션 `97a644712a37`, `76928652848e`, `983204074d73` |
| `ocr_status`, `confidence`, `low_confidence` 판정 | OCR 전용 필드·미리보기 응답 |

> ⚠️ 동기 미리보기 방식: OCR은 worker 배치(`ocr_worker.py`)가 아니라 **업로드 요청 내 동기 처리 →
> 미리보기 반환** 방식으로 구현되었다. 재처리(`reprocess`) API는 아직 미구현이다.

### 1.3 검진 등록 흐름 (현행 — OCR 기반)

OCR 미리보기 → 사용자 검토·수정 → 커밋 → 검수의 흐름으로 동작한다.

```
[1단계 업로드]  POST /records/checkups/upload (= ocr-preview)
                → Clova OCR + 파서 → 인식 수치 미리보기 (DB 미저장)
[2단계 커밋]    POST /records/checkups
                → CheckupRecord + CheckupMetricResult 저장
[3단계 검수]    POST /records/checkups/{id}/verify  (verification_status = VERIFIED)
[4단계 AI]      검수 완료 후 → 외부 분석 서버 요청 → 요약·위험도·미션 후보
```

- **이미지 업로드**: base64 이미지(다중 페이지) → OCR 처리 → 파싱된 수치 미리보기 반환.
- **커밋**: 사용자가 검토·수정한 수치로 `CheckupRecord` + metrics 저장. `is_edited` 보존.
- **직접 입력(`/manual`)·추이(`/trends`)**: 요구사항서에 명시되어 있으나 **아직 미구현**.
- **검수 게이트**(FR-HC-009, FR-AN-008)는 유지: `VERIFIED` 전에는 분석 API 호출 불가 (`409 NOT_VERIFIED`).

### 1.4 공통 규칙

- 응답 래퍼: `ApiResponse { success, message, data, error_code }`
- 인증: Bearer access token (Phase 1 이후 모든 비즈니스 API)
- 자동 로그인: refresh token — 디바이스 보안 저장소(iOS Keychain / Android Keystore)에 보관, `Authorization: Bearer`로 전송 (FR-AUTH-002)
- 발신 메일: `deundeun.dcsw@gmail.com` (FR-AUTH-003, D-010)
- 비밀번호: 8자 이상, 영문·숫자·특수문자 (FR-AUTH-004)

### 1.5 기술 스택 (팀 확정)

| 영역 | 선택 | 비고 |
|------|------|------|
| **Python** | **3.12.6** | `.python-version`, CI/Docker 3.12 |
| API | FastAPI **0.115.5** | `requirements.txt` |
| **DB** | **PostgreSQL 16** | JSONB·관계형, 로컬·운영 동일 |
| **ORM** | **SQLAlchemy 2.0.36** | `app/database/` |
| **DB 형상관리** | **Alembic 1.14.0** | `requirements.txt` 포함 |
| **배포** | **Docker Compose** | `python:3.12-slim` 베이스 이미지 |
| **이메일** | **SMTP** (Gmail) | 회원가입 인증·비밀번호 재설정 (Phase 1) |
| **인증** | JWT HS256 (30분 / refresh 14일) | Phase 1 |

버전·의존성 상세: [development-environment.md](./development-environment.md)

**Compose 구성 (예정)**

| 파일 | 용도 |
|------|------|
| `docker/docker-compose.yml` | 로컬 `postgres` + VM `--profile deploy` API |

로컬 개발 시 Postgres는 Compose로 띄우고, API는 컨테이너 또는 호스트에서 `uvicorn` 실행 가능.

**SMTP (Gmail) 설정 요약**

| 항목 | 값 |
|------|-----|
| Host | `smtp.gmail.com` |
| Port | `587` (STARTTLS) 권장 |
| Username | `deundeun.dcsw@gmail.com` |
| Password | Gmail **앱 비밀번호** (2단계 인증 후 발급) |
| From | `deundeun.dcsw@gmail.com` |

구현: `infrastructure/email/smtp_email_client.py` → `EmailClient` Protocol

### 1.6 확정 의사결정 (Phase 검토 반영)

| ID | 결정 | 비고 |
|----|------|------|
| D-BE-001 | ~~**OCR 미구현**~~ → **번복: OCR 구현 완료** (2026-06-26) | Clova·OcrJob·ocr_router 모두 구현됨 ([§1.2](#12-ocr-파이프라인-구현-완료-2026-06-26)) |
| D-BE-002 | **Phase 4 / 5 경계** | Phase 4: analysis callback·`mission_candidates` **저장·매핑만** / Phase 5: `UserMission` **생성 API** |
| D-BE-003 | **성장 API 경로** | 초기 결정은 **`/api/v1/growth/*` 단일화**였으나, 현재 구현(2026-07-02)은 `/api/v1/characters/me`, `/api/v1/characters/animals`를 프론트 사용 API로 채택 |
| D-BE-004 | **알림 API 분리** | **설정**: `GET/PATCH /api/v1/my/notification-settings` + `notification_preferences` (PR #35, **정본**). **알림함**: `GET /api/v1/notifications`, `PATCH /{id}/read` (Phase 7). `/notifications/settings`는 **구현하지 않음** |
| D-BE-005 | **검색 라우터** | 초기 계획은 `GET /search/medical-terms`. 현재 구현(2026-07-04)은 `GET /search/diseases` (의학 KG + AI) |
| D-BE-009 | **앱 정적 이미지 제공** | 시스템 이미지는 `image_assets` bytea에 저장하고 공개 GET URL로 제공. 이미지 원본과 seed 스크립트는 Git/Docker에 포함하지 않고 운영자가 SSH로 직접 등록 |

---

## 2. Phase 개요

```mermaid
flowchart LR
  P0[Phase 0\n기반] --> P1[Phase 1\nAuth]
  P1 --> P2[Phase 2\nOnboarding]
  P2 --> P3[Phase 3\nRecord]
  P3 --> P4[Phase 4\nAnalysis]
  P4 --> P5[Phase 5\nMission·Growth]
  P5 --> P6[Phase 6\nHome]
  P6 --> P7[Phase 7\nNotification]
  P7 --> P8[Phase 8\nMy·Search]
  P8 --> P9[Phase 9\nMedia]
```

| Phase | 이름 | 핵심 산출물 | 선행 |
|-------|------|-------------|------|
| 0 | 기반 인프라 | DB 마이그레이션, JWT 의존성, 이메일 클라이언트 | 0.5 스캐폴딩 |
| 1 | 인증·계정 | 로그인·회원가입·토큰·비밀번호 | Phase 0 |
| 2 | 온보딩 | 약관·웨어러블·단계 추적 | Phase 1 |
| 3 | 검진 기록 | 업로드·직접입력·수치·검수·조회 | Phase 2 |
| 4 | 외부 AI 분석 | 분석 job·callback·결과 저장 | Phase 3 |
| 5 | 미션·성장 | 미션·XP·레벨·캐릭터 | Phase 4 |
| 6 | 홈 | 화면용 Aggregation API | Phase 5 |
| 7 | 알림 | 알림함·설정·백그라운드 worker | Phase 6 |
| 8 | 마이·검색 | 프로필·설정·용어 검색·문의 | Phase 7 |
| 9 | 미디어 | 앱 정적 이미지 URL 제공 | Phase 1 |
| 9 | 미디어 | 캐릭터 이미지 연동 | Phase 5 |

---

## 3. Phase 0 — 기반 인프라

> 목표: Phase 1부터 비즈니스 로직을 쌓을 수 있는 **PostgreSQL + Alembic + Compose + SMTP** 기반을 확정한다.

### 3.1 MUST 구현

| 항목 | 상세 |
|------|------|
| **PostgreSQL 연결** | `DATABASE_URL=postgresql+psycopg2://user:pass@localhost:5432/deundeun` |
| **Alembic 셋업** | `alembic init` → `env.py`에 `app.database.base` 연동 → 첫 revision |
| **Docker Compose (로컬)** | `docker/docker-compose.yml` — `postgres` 서비스 + volume + healthcheck |
| `get_current_user` | JWT access token 검증, `user_id` 주입 |
| 환경 변수 | `DATABASE_URL`, `JWT_SECRET_KEY`, `JWT_ACCESS_EXPIRE_MINUTES`, `JWT_REFRESH_EXPIRE_DAYS` |
| **SMTP EmailClient** | `SmtpEmailClient` 구현 (개발 시 `.env`에 Gmail 앱 비밀번호) |
| 에러 코드 체계 | `EMAIL_ALREADY_EXISTS`, `NOT_VERIFIED`, `INVALID_CREDENTIALS` 등 `core/exceptions.py` 확정 |

### 3.1.1 의존성 (`requirements.txt`에 포함됨)

| 패키지 | 버전 | 용도 |
|--------|------|------|
| psycopg2-binary | 2.9.10 | PostgreSQL 드라이버 |
| alembic | 1.14.0 | 마이그레이션 |
| python-multipart | 0.0.12 | 검진 이미지 업로드 |
| httpx | 0.27.2 | 외부 분석 서버 HTTP |

개발·테스트: `requirements-dev.txt` — `testcontainers[postgresql]==4.8.2`, `pytest`, `ruff`

Phase 0 작업: `alembic init` + `tests/conftest.py`에 testcontainers 연동 (아직 미구현)

### 3.1.2 Alembic 워크플로

```bash
# 로컬 DB 기동
docker compose -f docker/docker-compose.yml up -d postgres

# 마이그레이션 적용
alembic upgrade head

# 모델 변경 후 revision 생성
alembic revision --autogenerate -m "add users table"
alembic upgrade head
```

- CI: GitHub Actions에 `postgres` service container 추가 후 `alembic upgrade head` + `pytest`
- 운영 VM: 배포 스크립트 또는 Compose up 전 `alembic upgrade head` 실행

### 3.1.3 Docker Compose (로컬) — 제안 스펙

```yaml
# docker/docker-compose.yml (Phase 0에서 추가)
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: deundeun
      POSTGRES_PASSWORD: deundeun
      POSTGRES_DB: deundeun
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U deundeun"]
      interval: 5s
      retries: 5

  api:                          # 선택 — 로컬 전체 컨테이너 실행 시
    build: ..
    ports:
      - "8000:8000"
    env_file: ../.env
    depends_on:
      postgres:
        condition: service_healthy

volumes:
  pgdata:
```

**VM 배포** (`docker compose --profile deploy`): API 이미지만 실행. DB는 동일 VM Postgres 또는 `DATABASE_URL`로 외부 DB 연결.

### 3.1.4 SMTP 구현 (Phase 0 stub → Phase 1 연동)

| 용도 | Phase | 메서드 |
|------|-------|--------|
| 회원가입 6자리 인증 코드 | 1 | `send_verification_email` |
| 비밀번호 재설정 | 1 | `send_password_reset_email` |
| 시스템 알림 (선택) | 7 | `send_notification_email` |

- Phase 0: `SmtpEmailClient` + 환경 변수 바인딩 (`core/config.py`)
- Phase 1: Auth API에서 실제 발송 호출
- 로컬 테스트: MailHog 등 SMTP 캡처 도구로 대체 가능 (Compose에 `mailhog` 서비스 추가 옵션)

### 3.2 초기 DB 테이블 (Phase 0~1)

```
users
email_verifications
refresh_tokens
consent_histories
```

### 3.3 Phase 3 이후 추가 테이블 (마이그레이션 분리 가능)

```
checkup_records          -- ocr_status, ocr_job_id 없음
checkup_metric_results
checkup_files
analysis_jobs
checkup_analysis_summaries
health_metric_references
mission_templates
user_missions
mission_completions
xp_ledger
growth_profiles
level_rules
character_catalog
user_characters
wearable_connections
notification_settings
notifications
medical_terms
```

### 3.4 완료 기준

- [ ] `docker compose -f docker/docker-compose.yml up -d postgres` 로컬 DB 기동
- [ ] `alembic upgrade head` 로컬·CI 통과
- [ ] SMTP 테스트 메일 1건 발송 성공 (또는 MailHog 캡처 확인)
- [ ] 인증 없는 보호 API → `401`
- [ ] `GET /health` 유지

---

## 4. Phase 1 — 인증·계정 (Auth + User)

> 목표: 로그인·회원가입·세션 전체를 동작시킨다.  
> 대응 화면: AU-001, AU-002, AU-003, SP-001(세션 검증)

### 4.1 API 목록

| 우선순위 | Method | Path | 설명 | 요구사항 |
|----------|--------|------|------|----------|
| MUST | POST | `/api/v1/auth/email/verify/request` | 6자리 인증 코드 발송 | FR-AUTH-003 |
| MUST | POST | `/api/v1/auth/email/verify/confirm` | 인증 코드 확인 | FR-AUTH-003 |
| MUST | POST | `/api/v1/auth/signup` | 계정 생성 (인증 완료 후) | FR-AUTH-005 |
| MUST | POST | `/api/v1/auth/login` | 로그인 → access + refresh | FR-AUTH-001 |
| MUST | POST | `/api/v1/auth/refresh` | access token 재발급 | FR-AUTH-002 |
| MUST | POST | `/api/v1/auth/logout` | 현재 refresh 폐기 | FR-AUTH-007 |
| MUST | POST | `/api/v1/auth/password/reset/request` | 재설정 메일 발송 | FR-AUTH-006 |
| MUST | POST | `/api/v1/auth/password/reset/confirm` | 재설정 완료 + 전체 refresh 폐기 | FR-AUTH-006 |
| MUST | GET | `/api/v1/auth/me` | 내 프로필 조회 | — |
| SHOULD | — | 로그인 실패 잠금 | N회 실패 시 일시 잠금 | FR-AUTH-008 |

> **경로 참고**: 요구사항서의 `/auth/email-codes` 는 현재 라우터 `/auth/email/verify/*` 와 동일 역할. 구현 시 **기존 stub 경로 유지** 권장.

### 4.2 도메인·파일

```
domains/auth/     models, repository, service, schemas, exceptions
domains/user/     User 모델, nickname, timezone, status, onboarding_step
infrastructure/email/
  email_client.py       — Protocol + StubEmailClient
  smtp_email_client.py  — SmtpEmailClient (SMTP 필수)
core/security.py  — password hash, JWT encode/decode
core/dependencies.py — get_current_user
core/config.py    — DATABASE_URL, SMTP_* 설정
```

### 4.3 핵심 비즈니스 규칙

| 규칙 | 구현 위치 |
|------|-----------|
| 이메일 중복 → `409 EMAIL_ALREADY_EXISTS` | `AuthService.signup` |
| 인증 코드 만료·오입력·재전송 제한 | `EmailVerification` + policy |
| 비밀번호 정책 검증 (서버) | `AuthService` + Pydantic validator |
| refresh token 회전·`revoked_at` 폐기 | `AuthService.refresh`, `logout` |
| 비밀번호 재설정 시 모든 refresh 폐기 | `password/reset/confirm` |

### 4.4 Request/Response 스키마 (요약)

**POST `/auth/signup`**

```json
{
  "email": "user@example.com",
  "password": "Passw0rd!",
  "nickname": "든든이",
  "verification_token": "..."
}
```

**POST `/auth/login`**

```json
{ "email": "user@example.com", "password": "Passw0rd!" }
```

**Response `data`**

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "expires_in": 900,
  "user": { "id": 1, "email": "...", "nickname": "...", "onboarding_step": "CONSENT" }
}
```

### 4.5 완료 기준 (테스트)

- [ ] TC-002 인증 코드 만료·재전송
- [ ] TC-003 유효 refresh → 자동 로그인
- [ ] TC-018 비밀번호 재설정 후 refresh 무효
- [ ] 중복 가입 409

---

## 5. Phase 2 — 온보딩 (Onboarding + Wearable)

> 목표: 가입 후 약관·선택 연동·단계 재진입을 지원한다.  
> 대응 화면: CO-001, IN-001, ON-001  
> **현황(2026-06-26): 구현 완료** — 약관 동의(`/auth/policies/agree`), 온보딩 상태(`/onboarding/status`), 웨어러블 CONNECT/SKIP(`/onboarding/wearable`), 완료(`/onboarding/complete`). 마이그레이션 `007_add_wearable_connections`. `PATCH /my/wearable/{provider}`는 Phase 8.

### 5.1 API 목록

| 우선순위 | Method | Path | 설명 | 요구사항 |
|----------|--------|------|------|----------|
| MUST | POST | `/api/v1/auth/policies/agree` | 필수 약관 동의 기록 | FR-ONB-001 |
| MUST | GET | `/api/v1/onboarding/status` | 현재 `onboarding_step` 조회 | FR-ONB-004 |
| MUST | POST | `/api/v1/onboarding/wearable` | 건강 앱 연결 (또는 SKIP) | FR-ONB-002, FR-INT-001 |
| MUST | POST | `/api/v1/onboarding/complete` | 온보딩 완료 (검진·검수 후) | FR-ONB-003 |
| SHOULD | PATCH | `/api/v1/my/wearable/{provider}` | 연동 해제·상태 변경 | FR-INT-004 |

### 5.2 `onboarding_step` enum (제안)

```
CONSENT → WEARABLE → INITIAL_CHECKUP → CHECKUP_VERIFIED → COMPLETED
```

- `GET /onboarding/status` 가 클라이언트 라우팅 기준 (FR-ONB-004)
- 단계 전이: `agree_policies` → `CONSENT`에서만 가능, 성공 시 `WEARABLE`. `wearable`(CONNECT/SKIP) → `WEARABLE`에서만 가능, 성공 시 `INITIAL_CHECKUP`.
- `INITIAL_CHECKUP → CHECKUP_VERIFIED`는 Phase 3 검진 검증 시 전이. `complete`는 `CHECKUP_VERIFIED`에서만 가능.
- 단계 불일치 시 `409 INVALID_ONBOARDING_STEP`, 이미 완료 시 `409 ONBOARDING_ALREADY_COMPLETED`, 검증 전 완료 요청 시 `409 ONBOARDING_INCOMPLETE`.
- `WEARABLE` 단계는 skip 허용 → 연결 레코드를 만들지 않고 단계만 진행

### 5.3 약관 동의

**POST `/auth/policies/agree`**

```json
{
  "consents": [
    { "consent_type": "TERMS_OF_SERVICE", "version": "1.0", "agreed": true },
    { "consent_type": "PRIVACY", "version": "1.0", "agreed": true },
    { "consent_type": "HEALTH_DATA", "version": "1.0", "agreed": true }
  ]
}
```

- 필수 3종 미동의 시 `400 CONSENT_REQUIRED`
- 동의 버전이 `CURRENT_POLICY_VERSIONS`와 다르면 `400 POLICY_VERSION_MISMATCH`

### 5.4 Wearable (네이티브)

네이티브 앱이므로 OS 헬스 플랫폼을 통해 연동한다. HealthKit/Health Connect는 서버용 API가 없어
앱이 온디바이스에서 권한을 처리하고, 백엔드는 연결 상태와 승인 scope만 저장한다(실데이터 push는 후속 Phase).

| provider | 대상 OS | status | 비고 |
|----------|---------|--------|------|
| APPLE_HEALTH | iOS (HealthKit) | CONNECTED / DISCONNECTED / ERROR | 1차 주요 연동 대상 |
| SAMSUNG_HEALTH | Android (Health Connect) | CONNECTED / DISCONNECTED / ERROR | Android 대응 시 |
| GOOGLE_FIT | Android (Health Connect) | CONNECTED / DISCONNECTED / ERROR | Android 대응 시 |

- 요청: `{ "action": "CONNECT"|"SKIP", "provider": <enum|null>, "scopes": [..] }`. CONNECT 시 `provider` 필수(미지정 시 `422`).
- `WearableConnection` 저장 (FR-INT-001), `(user_id, provider)` 유니크. 재연결 시 upsert.
- SKIP은 레코드를 만들지 않고 단계만 진행.
- 동기화 worker는 Phase 7 SHOULD.

### 5.5 완료 기준

- [x] 필수 약관 없이 다음 단계 불가 (`400 CONSENT_REQUIRED` / `400 POLICY_VERSION_MISMATCH`)
- [x] wearable CONNECT/SKIP 후 검진 단계(`INITIAL_CHECKUP`) 진입
- [x] 앱 재진입 시 `GET /onboarding/status`로 `onboarding_step` 복원
- [x] 단계 가드(`409 INVALID_ONBOARDING_STEP` / `409 ONBOARDING_ALREADY_COMPLETED`)
- [x] 통합 테스트 `tests/test_onboarding_flow.py`

---

## 6. Phase 3 — 검진 기록 (Record + OCR)

> 목표: 이미지 업로드(OCR 인식)·수치 수정·검수·조회를 완성한다.  
> 대응 화면: HC-001, HC-002, HC-004, HC-005  
> **구현 상태(2026-06-27)**: Phase 3 MUST **구현 완료**. 설계 결정 D-BE-006(이미지 비저장)·D-BE-007(수치 전용 UI)·D-BE-008(커밋≠검수) 반영. SHOULD 잔여: meals·OCR reprocess.

### 6.1 API 목록

| 상태 | Method | Path | 설명 | 요구사항 |
|------|--------|------|------|----------|
| ✅ 구현 | POST | `/api/v1/records/checkups/upload` | 이미지 업로드 → OCR 미리보기 (= `ocr-preview`) | FR-HC-001, FR-HC-004 |
| ✅ 구현 | POST | `/api/v1/records/checkups/ocr-preview` | OCR 인식 결과 미리보기 (DB 미저장, `content_hash` 포함) | FR-HC-001, FR-HC-010 |
| ✅ 구현 | POST | `/api/v1/records/checkups` | 미리보기 수치 커밋 → record + metrics (`UNVERIFIED`) | FR-HC-001, FR-HC-012 |
| ✅ 구현 | POST | `/api/v1/records/checkups/manual` | 직접 수치 입력으로 record 생성 | FR-HC-012 |
| ✅ 구현 | GET | `/api/v1/records/checkups` | 검진 목록 (페이지네이션) | FR-HC-013 |
| ✅ 구현 | GET | `/api/v1/records/checkups/{record_id}` | 검진 상세 (status·reference enrich) | FR-HC-014 |
| ✅ 구현 | GET | `/api/v1/records/checkups/{record_id}/trends` | 지표별 추이 | FR-HC-015 |
| ✅ 구현 | GET | `/api/v1/records/checkups/{record_id}/metrics` | 수치 목록 | FR-HC-007 |
| ✅ 구현 | PATCH | `/api/v1/records/checkups/{record_id}/metrics/{metric_id}` | 단일 수치 수정 | FR-HC-007 |
| ✅ 구현 | PUT | `/api/v1/records/checkups/{record_id}/metrics` | 수치 일괄 수정 | FR-HC-007 |
| ✅ 구현 | POST | `/api/v1/records/checkups/{record_id}/verify` | 검수 완료 → VERIFIED, metric 평가 DB freeze | FR-HC-009 |
| ✅ 구현 | DELETE | `/api/v1/records/checkups/{record_id}` | 검진 삭제 | FR-HC-016 |
| ✅ 구현 | GET | `/api/v1/ocr/jobs/{job_id}` | OCR job 상태 조회 | — |
| ⬜ 미구현 | POST | `/api/v1/onboarding/checkup` | 별도 API 없음 — `RecordService.verify` 훅으로 대체 | FR-ONB-003 |
| ⬜ 미구현 | POST/GET | `/api/v1/records/meals` | 식사 기록 (Phase 3+ SHOULD) | — |

> **잔여 SHOULD**: OCR `reprocess`(FR-HC-006은 `manual` 직접 입력으로 대체 가능), meals.

### 6.2 업로드 API (OCR 미리보기)

**POST `/records/checkups/upload`** (내부적으로 `ocr-preview`와 동일 핸들러)

- 요청: base64 인코딩 이미지 배열(다중 페이지, `max_images_per_upload` 제한).
- 처리: 이미지 포맷·크기 검증 → Clova OCR → 규칙 파서 → 인식 수치 추출. **이 단계에서는 DB에 저장하지 않으며 이미지 bytes는 폐기한다 (D-BE-006).**
- 응답: 페이지 수, 실패 페이지, `ocr_status`, `content_hash`, 파싱된 metrics 미리보기.

```json
{
  "page_count": 2,
  "failed_pages": [],
  "ocr_status": "COMPLETED",
  "content_hash": "a1b2c3...",
  "metrics": [
    { "metric_code": "fasting_glucose", "metric_name": "공복혈당", "value": "126", "unit": "mg/dL", "confidence": 0.92, "low_confidence": false, "page_index": 0 }
  ]
}
```

### 6.3 커밋 API

**POST `/records/checkups`** — 미리보기에서 검토·수정한 수치를 실제로 저장한다.

```json
{
  "ocr_status": "COMPLETED",
  "failed_pages": [],
  "content_hash": "a1b2c3...",
  "metrics": [
    { "metric_code": "fasting_glucose", "metric_name": "공복혈당", "value": "120", "unit": "mg/dL", "confidence": 0.92, "raw_text": "126", "page_index": 0, "is_edited": true }
  ]
}
```

- `verification_status=UNVERIFIED`로 record 생성, `is_edited` 보존, `(user_id, file_hash)` 중복 시 기존 record 반환
- `POST .../manual` 직접 입력: OCR 없이 동일 record + metrics 저장 (`ocr_status=COMPLETED`)

### 6.4 검수 API

**POST `/records/checkups/{record_id}/verify`**

```json
{
  "metrics": [
    { "metric_id": 1, "value": "26.0" }
  ]
}
```

- `verification_status` → `VERIFIED`, `verified_at` 기록
- 모든 metric에 `status`·`reference_min/max`를 검수 시점 기준으로 DB에 freeze
- 이후 Phase 4 분석 요청 허용

### 6.5 CheckupRecord 필드

| 필드 | 값 | 비고 |
|------|-----|------|
| `source_type` | UPLOAD / MANUAL | |
| `verification_status` | UNVERIFIED → VERIFIED | 검수 게이트 |
| `analysis_status` | PENDING → COMPLETED / FAILED | Phase 4 |
| `ocr_status` | PENDING / COMPLETED / FAILED | **OCR 구현으로 사용** |
| `file_hash` | SHA-256 | 중복 방지 (FR-HC-010) |

### 6.6 CheckupMetricResult 필드

| 필드 | 설명 |
|------|------|
| `source` | OCR / MANUAL / ANALYSIS |
| `is_edited` | 사용자 수정 여부 (OCR 인식값 대비) |
| `status` | NORMAL / CAUTION / RISK / UNKNOWN |
| `confidence`, `raw_text`, `page_index` | **OCR 인식 메타데이터 — 구현으로 사용** |

### 6.7 HealthMetric (같은 Phase 또는 3.5)

| 우선순위 | 내용 | 구현 |
|----------|------|------|
| MUST | `health_metric_references` seed (18종 기준·설명) | ✅ migration `008` |
| MUST | 상세·추이 응답 시 기준 범위·상태 코드 조합 | ✅ 조회 시 enrich, verify 시 DB freeze |

### 6.8 인프라

```
infrastructure/ocr/  — Clova·파서·지표 사전 (✅)
domains/record/service.py, repository.py, policy.py (✅)
```

> **D-BE-006**: `infrastructure/storage/file_storage.py`는 **구현하지 않음**. 검진 이미지는 OCR 처리 후 폐기.

### 6.9 완료 기준 (테스트)

- [x] TC-004 업로드 → record 생성 (ocr-preview는 DB 미저장)
- [x] TC-005 중복 file_hash → 200 기존 record
- [x] TC-008 수치 수정 + `is_edited` 보존
- [x] TC-009 미검수 record → analysis 409
- [x] TC-019 타 사용자 record → 403/404
- [x] 직접 입력 → verify → metrics 조회

---

## 7. Phase 4 — 외부 AI 분석 (Analysis)

> 목표: 검수 완료된 기록에 대해 외부 분석 서버 연동·결과 저장.  
> 대응 화면: AN-001, HC-003, HC-006

### 7.1 API 목록

| 우선순위 | Method | Path | 설명 | 요구사항 |
|----------|--------|------|------|----------|
| MUST | POST | `/api/v1/analysis/checkups/{record_id}` | 분석 요청 생성 | FR-AN-001, FR-AN-008 |
| MUST | GET | `/api/v1/analysis/jobs/{analysis_job_id}` | 분석 상태 폴링 | FR-AN-002 |
| MUST | GET | `/api/v1/analysis/jobs/{analysis_job_id}/result` | 분석 결과 조회 | FR-AN-005 |
| MUST | POST | `/api/v1/analysis/callback` | 외부 서버 callback (서명 검증) | FR-AN-003, FR-AN-007 |

> **Phase 4 범위 밖** (Phase 5): `POST /records/checkups/{record_id}/missions` — `UserMission` 생성은 [§8](#8-phase-5--미션성장-mission--character--growth) 참고 (D-BE-002).

### 7.2 분석 상태

```
PENDING → PROCESSING → COMPLETED
                    → FAILED
```

- 허용되지 않은 전이 거부 (FR-AN-002)
- hard timeout 180초 → FAILED 또는 재시도 (NFR-003)

### 7.3 검수 게이트

```python
# domains/analysis/service.py
AnalysisService.ensure_verified(record)  # NOT_VERIFIED → 409
```

### 7.4 Callback 멱등성

- 동일 `external_job_id` callback 반복 → 결과 중복 생성 없음 (FR-AN-003, TC-012)
- `X-Analysis-Signature` 또는 서비스 토큰 검증 (FR-AN-007)

### 7.5 외부 서버 연동

```
infrastructure/external_analysis/analysis_client.py
  StubAnalysisClient → HttpAnalysisClient (환경 변수 연동)
workers/analysis_result_worker.py  — callback 미수신 시 polling 보조 (FR-AN-004)
```

**환경 변수**

```
ANALYSIS_SERVER_BASE_URL
ANALYSIS_SERVER_API_KEY
ANALYSIS_CALLBACK_SECRET
```

### 7.6 분석 결과 저장

| 저장 대상 | 내용 |
|-----------|------|
| `CheckupAnalysisSummary` | summary, risk_level, positive/caution points, recommendations |
| `CheckupMetricResult` | 분석 서버가 반환한 metrics (upsert, source=ANALYSIS) |
| `AnalysisJob` | model_version, raw_result_url |

### 7.7 미션 후보 매핑 (저장만 — UserMission 생성은 Phase 5)

- callback `mission_candidates[].template_code` → `MissionTemplate` 존재 여부 검증
- 템플릿에 없는 코드는 **무시** (FR-AN-006)
- 검증된 후보는 `CheckupAnalysisSummary` 연관 필드 또는 `analysis_mission_candidates` 테이블에 **저장**
- 사용자 미션 배정(`UserMission`)은 **Phase 5** `POST /records/checkups/{record_id}/missions` 에서 수행

### 7.8 완료 기준 (테스트)

- [ ] TC-009 검수 전 분석 요청 409
- [ ] TC-011 분석 COMPLETED 후 결과 조회
- [ ] TC-012 중복 callback 멱등
- [ ] TC-013 실패·재시도 attempt 증가
- [ ] Stub → Http 클라이언트 교체 가능

---

## 8. Phase 5 — 미션·성장 (Mission + Character + Growth)

> 목표: 홈·실천 화면의 핵심 루프 — 미션 배정·완료·XP·레벨·캐릭터.  
> 대응 화면: MI-001, MI-002, GR-001

### 8.1 API 목록 — Mission

| 우선순위 | Method | Path | 설명 | 요구사항 |
|----------|--------|------|------|----------|
| MUST | GET | `/api/v1/missions/today` | 오늘의 미션 (로컬 날짜) | FR-MIS-001 |
| MUST | POST | `/api/v1/missions/{mission_id}/complete` | SELF_CHECK 완료 | FR-MIS-004 |
| MUST | POST | `/api/v1/missions/{mission_id}/verify` | PHOTO_UPLOAD 증빙·완료 | FR-MIS-005 |
| MUST | GET | `/api/v1/missions/calendar` | 주간/월간 미션 캘린더 | FR-MIS-008 |
| MUST | GET | `/api/v1/missions/statistics/weekly` | 완료율·추이 | FR-MIS-009 |
| MUST | POST | `/api/v1/records/checkups/{record_id}/missions` | 분석 추천 → UserMission 생성 | FR-AN-006, FR-MIS-003 |
| SHOULD | — | HEALTH_DATA 자동 완료 | 웨어러블 연동 시 | FR-MIS-006 |

### 8.2 API 목록 — Growth / Character

> 현재 구현(2026-07-02): 별도 `/growth/*` 라우터는 만들지 않고 `/api/v1/characters/me`, `/api/v1/characters/animals`를 사용한다. 레벨업은 대표 캐릭터 변경이 아니라 보유 동물 컬렉션 누적 해금으로 해석한다.

| 우선순위 | Method | Path | 설명 | 요구사항 |
|----------|--------|------|------|----------|
| MUST | GET | `/api/v1/growth` | XP·레벨·streak·대표 캐릭터 요약 | FR-GRW-001 |
| MUST | GET | `/api/v1/growth/characters` | 획득 캐릭터 목록 | FR-GRW-004 |
| MUST | PUT | `/api/v1/growth/characters/{id}/primary` | 대표 캐릭터 변경 | FR-GRW-004 |
| MUST | — | `XpLedger` 기록 | 미션 완료 시 원장 1건 | FR-GRW-006, FR-MIS-007 |
| MUST | — | `level_rules` seed + 레벨 계산 | 서버 기준 | FR-GRW-002 |
| MUST | — | 레벨업 이벤트·알림 1회 | XP 임계 통과 시 | FR-GRW-003 |
| MUST | — | streak 갱신 | 하루 1회만 증가 | FR-MIS-010 |

> **라우터 정리 현황**: 현재는 `character_router`가 프론트 사용 API로 승격되었고 `/growth/*`는 미생성이다. `/growth/*` 재도입 여부는 미션 완료·EXP 루프 확장 시 별도 결정한다.

> 범위가 크면 서브 이슈: **5a Mission** / **5b Growth·Character** ([phase-review](./issues/phase-review.md))

### 8.3 미션 완료 규칙

| 검증 방식 | 완료 조건 |
|-----------|-----------|
| SELF_CHECK | 확인 API 1회 |
| PHOTO_UPLOAD | 증빙 파일 업로드 후 complete |
| HEALTH_DATA | wearable 목표 충족 (SHOULD) |

- 동일 미션 중복 완료·XP 중복 지급 방지 — DB 유니크 + `XpLedger` (FR-MIS-007, TC-014)
- 온보딩 완료 시 기본 캐릭터·GrowthProfile 생성 (FR-ONB-003)

### 8.4 MissionTemplate seed

- 운영 승인 템플릿 DB seed (FR-MIS-011)
- `code`, `title`, `category`, `verification_mode`, `default_xp`, `active`

### 8.5 완료 기준 (테스트)

- [ ] TC-014 미션 중복 완료 → XP 1회
- [ ] TC-015 같은 날 여러 미션 → streak +1만
- [ ] TC-016 레벨업 이벤트·알림 1회
- [ ] 추천 미션 → `UserMission` 생성, 동일일·템플릿 중복 방지

---

## 9. Phase 6 — 홈 (Home Aggregation)

> 목표: 홈 화면 1~2회 호출로 필요 데이터 제공.  
> 대응 화면: HO-001

### 9.1 API 목록

| 우선순위 | Method | Path | 설명 |
|----------|--------|------|------|
| MUST | GET | `/api/v1/home` | 홈 통합 (미션·성장·알림 요약) |
| SHOULD | GET | `/api/v1/home/summary` | 경량 요약만 |

### 9.2 `GET /home` 응답 구성 (제안)

```json
{
  "user": { "nickname": "...", "onboarding_completed": true },
  "growth": { "level": 3, "xp_total": 450, "streak_current": 5 },
  "primary_character": { "code": "sprout", "image_url": "..." },
  "today_missions": {
    "total": 3,
    "completed": 1,
    "items": [ "..."]
  },
  "unread_notification_count": 2
}
```

- `domains/home/service.py` — Mission·Character·Notification 서비스 조합만, DB 직접 접근 최소화

### 9.3 완료 기준

- [ ] 홈 값 = 개별 API 값과 일치 (FR-GRW-001)
- [ ] p95 2초 이내 (NFR-001)

---

## 10. Phase 7 — 알림함 (Notification Inbox + Triggers)

> 목표: 알림함·읽음·이벤트 기반 inbox 생성·Home unread. **알림 설정은 My API 정본**(D-BE-004).  
> 대응 화면: NO-001  
> 상세: [issues/phase-7.md](./issues/phase-7.md)

### 10.1 API 목록

| 우선순위 | Method | Path | 설명 | 요구사항 |
|----------|--------|------|------|----------|
| MUST | GET | `/api/v1/notifications` | 알림 목록 (페이지네이션) | FR-ETC-002 |
| MUST | PATCH | `/api/v1/notifications/{id}/read` | 읽음 처리 | FR-ETC-002 |
| — | GET/PATCH | `/api/v1/notifications/settings` | **구현 안 함** — stub 제거. 설정은 `/my/notification-settings` | — |
| — | POST | `/api/v1/notifications/test` | **구현 안 함** — 제거 | — |

**이미 구현 (Phase 7 범위 밖, PR #35)**

| Method | Path | 설명 |
|--------|------|------|
| GET/PATCH | `/api/v1/my/notification-settings` | 알림 설정 조회·변경 (`notification_preferences`) |

### 10.2 알림 유형

| type | 트리거 | MVP |
|------|--------|-----|
| ANALYSIS_COMPLETED | `POST /health-metrics/analyses` 저장 성공 | MUST |
| LEVEL_UP | `CharacterService.gain_exp` → `leveled_up=True` | MUST |
| MISSION_REMINDER | notification scheduler (7b) | SHOULD |
| RECORD_REMINDER | notification scheduler (7b) | SHOULD |
| WEEKLY_REPORT | notification scheduler (7b) | SHOULD |

> **범위 경계**: `POST /missions/{id}/complete`는 상태 전이 + `gain_exp` 호출 + 레벨업 시 `LEVEL_UP` 알림까지 수행함(연결 완료). legacy `/analysis/callback`은 ANALYSIS_COMPLETED 트리거에서 제외.

### 10.3 Workers (Phase 7b)

```
workers/mission_notification_worker.py
workers/record_reminder_worker.py
```

- 리마인드·주간 리포트는 7b. `mission/scheduler.py`는 **미션 생성용**(Phase 5)이며 알림 worker와 별개.
- 비활성화 사용자 skip — `notification_preferences` (FR-MIS-012, 7b 리마인드만)
- 딥링크 `deep_link` 필드 (FR-ETC-002)

### 10.4 완료 기준

- [ ] HealthMetric 분석 저장 시 inbox 1건 생성
- [ ] `gain_exp` 레벨업 시 inbox 1건 (미션 complete 경로는 별도 Phase 5)
- [ ] 읽음 처리 후 Home `unread_notification_count` 감소
- [ ] `/my/notification-settings` 동작 유지

---

## 11. Phase 8 — 마이페이지·검색·지원 (My + Search + Support)

> 목표: 설정·프로필·용어 검색·문의.  
> 대응 화면: MY-001~003, SE-001

### 11.1 API 목록 — My

| 우선순위 | Method | Path | 설명 | 요구사항 |
|----------|--------|------|------|----------|
| MUST | GET | `/api/v1/my/profile` | 프로필 조회 | FR-ETC-005 |
| MUST | PATCH | `/api/v1/my/profile` | 닉네임·timezone 등 | FR-ETC-005 |
| MUST | PATCH | `/api/v1/my/password` | 비밀번호 변경 + 전체 세션 만료 | FR-ETC-006 |
| MUST | GET/PATCH | `/api/v1/my/wearable` | 연동 앱 관리 | FR-INT-004 |
| SHOULD | GET/PATCH | `/api/v1/my/app-lock` | 앱 잠금 설정 | |
| SHOULD | POST | `/api/v1/my/support` | 문의 접수 | |
| SHOULD | DELETE | `/api/v1/my/account` | 회원 탈퇴 | |

> 알림 설정은 **`GET/PATCH /api/v1/my/notification-settings`** (D-BE-004, PR #35 구현 완료). 연동 앱은 `GET/PATCH /my/connected-apps`.

### 11.2 API 목록 — Search (신규 라우터)

| 우선순위 | Method | Path | 설명 | 요구사항 |
|----------|--------|------|------|----------|
| MUST | GET | `/api/v1/search/medical-terms?q=` | 검진 용어 검색 | FR-ETC-003, FR-ETC-004 |

- `medical_terms` seed (승인된 사전만)
- 일반 질문·웹 검색 결과 반환 금지
- 빈 결과 시 추천 키워드 (SHOULD)

**Response 예시**

```json
{
  "items": [
    {
      "term": "공복혈당",
      "definition": "...",
      "simple_explanation": "...",
      "related_metric_codes": ["fasting_glucose"]
    }
  ],
  "suggested_keywords": ["혈당", "당뇨"]
}
```

### 11.3 감사 로그 (SHOULD)

- 비밀번호 변경, 연동 해제, 검진 삭제 (NFR-012)

### 11.4 완료 기준 (테스트)

- [ ] TC-017 사전 외 검색 → 빈 결과
- [ ] TC-018 비밀번호 변경 → 전 refresh 폐기
- [ ] 프로필·알림 설정 즉시 반영

---

## 12. Phase 9 — 앱 미디어/정적 이미지 (Media)

> 목표: 동물 도감·UI 이미지 등 앱 정적 리소스를 URL로 제공한다.

### 12.1 API 목록

| 우선순위 | Method | Path | 설명 |
|----------|--------|------|------|
| MUST | GET | `/api/v1/media/images` | 시스템 이미지 메타 목록 |
| MUST | GET | `/api/v1/media/images/{image_id}` | 시스템 이미지 바이너리 |
| MUST | GET | `/api/v1/media/images/{image_id}/meta` | 시스템 이미지 메타 |
| MUST | GET | `/api/v1/media/images/by-key/{purpose}/{asset_key}` | key 기반 이미지 바이너리 |
| MUST | GET | `/api/v1/media/images/by-key/{purpose}/{asset_key}/meta` | key 기반 이미지 메타 |

### 12.2 운영 결정

- 앱 정적 이미지는 `image_assets.data` bytea에 저장한다.
- 시스템 이미지는 프론트 `<img src>` 직접 사용을 위해 인증 없이 공개 GET으로 제공한다.
- 이미지 원본과 seed 스크립트는 Git/Docker image에 포함하지 않는다.
- 운영자가 SSH로 `/opt/deundeun/media-seed`에 이미지와 seed 스크립트를 올려 DB에 등록한다.
- 사용자 업로드 미디어, OCR 원본 저장, S3/MinIO/CDN은 후속 Phase 9b로 분리한다.

### 12.3 Character 연동

`GET /api/v1/characters/me`, `GET /api/v1/characters/animals` 응답에 동물별 `image_urls`를 포함한다.

---

## 13. Phase별 의존성·병렬 가능 여부

| Phase | 단독 착수 | 비고 |
|-------|-----------|------|
| 0 | ✅ | DB 없이는 1 불가 |
| 1 | ✅ | MVP 첫 마일스톤 |
| 2 | Phase 1 후 | |
| 3 | Phase 1 후 | 온보딩과 병렬 가능 (인증만 필요) |
| 4 | Phase 3 후 | verify 게이트 |
| 5 | Phase 4 후 | 추천 미션 연동; 기본 미션만이면 3 후 일부 가능 |
| 6 | Phase 5 후 | |
| 7 | Phase 5 후 | 알림 트리거는 4·5 필요 |
| 8 | Phase 1 후 | 검색·마이는 독립 가능, 통합은 후반 |
| 9 | Phase 1 후 | 공개 시스템 이미지 조회는 독립 가능, Character 연동은 Phase 5 후 |

**권장 개발 순서**: `0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9`

**첫 세로 슬라이스** (요구사항서 §13):

```
로그인 → 직접 수치 입력 → verify → (Stub) AI 분석 callback
→ 결과 확인 → 미션 1개 생성 → 완료 → XP 반영 → 홈
```

→ Phase **1 + 3 + 4 + 5 + 6** 최소 구현으로 E2E 가능.

---

## 14. API 전체 목록 (구현 체크리스트)

### Auth `/api/v1/auth`

- [ ] POST `/email/verify/request`
- [ ] POST `/email/verify/confirm`
- [ ] POST `/signup`
- [ ] POST `/login`
- [ ] POST `/refresh`
- [ ] POST `/logout`
- [ ] POST `/password/reset/request`
- [ ] POST `/password/reset/confirm`
- [ ] POST `/policies/agree`
- [ ] GET `/me`

### Onboarding `/api/v1/onboarding`

- [ ] GET `/status`
- [ ] POST `/checkup`
- [ ] POST `/wearable`
- [ ] POST `/complete`

### Record `/api/v1/records`

- [x] POST `/checkups/upload` (OCR 미리보기)
- [x] POST `/checkups/ocr-preview`
- [x] POST `/checkups` (커밋)
- [ ] POST `/checkups/manual` *(미구현)*
- [ ] GET `/checkups` *(미구현)*
- [ ] GET `/checkups/{record_id}` *(미구현)*
- [x] GET `/checkups/{record_id}/metrics`
- [x] PATCH `/checkups/{record_id}/metrics/{metric_id}`
- [x] PUT `/checkups/{record_id}/metrics`
- [x] POST `/checkups/{record_id}/verify`
- [ ] GET `/checkups/{record_id}/trends` *(미구현)*
- [x] DELETE `/checkups/{record_id}`

### OCR `/api/v1/ocr` *(구현 완료, D-BE-001 번복)*

- [x] GET `/jobs/{job_id}` — OCR job 상태 조회

### HealthMetric `/api/v1/health-metrics` *(신규 — CAG 분석, PR #5)*

- [x] POST `/evaluate` — 입력 수치 기준 평가(정상/주의/위험)
- [x] POST `/analyses` — 건강 항목 분석 결과 생성·저장

> `health_metric` 도메인은 `HealthMetricReference`(기준값 seed) + `HealthMetricAnalysis`(평가 결과)로 구성된다.
> 마이그레이션 `004_add_health_metric_analyses`, `005_add_health_metric_analysis_measured_at` 적용됨.

### Analysis `/api/v1/analysis` (Phase 4)

- [ ] POST `/checkups/{record_id}`
- [ ] GET `/jobs/{analysis_job_id}`
- [ ] GET `/jobs/{analysis_job_id}/result`
- [ ] POST `/callback`

### Mission `/api/v1/missions` (Phase 5)

- [x] GET `/today`
- [x] POST `/{mission_id}/complete` — self-report + `gain_exp` 지급 + `LEVEL_UP` 알림
- [x] DELETE `/{mission_id}/complete` — 완료 취소 + EXP 회수
- [ ] POST `/{mission_id}/verify` — 웨어러블 자동 인증
- [x] GET `/calendar`
- [x] GET `/statistics/weekly`
- [ ] POST `/api/v1/records/checkups/{record_id}/missions` — 추천 미션 생성

### Growth `/api/v1/growth` (Phase 5)

- [x] `/api/v1/characters/me` — 성장 요약과 보유 동물 목록
- [x] `/api/v1/characters/animals` — 전체 동물 카탈로그와 잠금/해금 상태
- [ ] PUT `/characters/{id}/primary`

### Home `/api/v1/home` (Phase 6)

- [x] GET `/`
- [x] GET `/summary` (SHOULD)

### Notification `/api/v1/notifications` (Phase 7)

- [ ] GET `/` — 알림함 목록
- [ ] PATCH `/{id}/read` — 읽음
- [x] 설정 — `/my/notification-settings` (My 정본, Phase 7에서 `/notifications/settings` 미구현)
- [ ] `/settings`, `/test` stub 제거

### My `/api/v1/my`

- [x] GET/PATCH `/connected-apps`
- [x] GET/PATCH `/notification-settings`
- [ ] GET `/profile`
- [ ] PATCH `/profile`
- [ ] PATCH `/password`
- [ ] GET/PATCH `/app-lock`
- [ ] POST `/support`
- [ ] DELETE `/account`

### Search `/api/v1/search` *(신규 라우터)*

- [ ] GET `/medical-terms`

### OCR 재처리 (미구현)

- [x] GET `/api/v1/ocr/jobs/{job_id}` — 구현됨 (위 OCR 섹션)
- [ ] POST `/api/v1/ocr/checkups/{record_id}/reprocess` — 재처리 API는 미구현

---

## 14. 환경 변수 체크리스트

| 변수 | Phase | 필수 | 설명 |
|------|-------|------|------|
| `DATABASE_URL` | 0 | ✅ | `postgresql+psycopg2://deundeun:deundeun@localhost:5432/deundeun` |
| `JWT_SECRET_KEY` | 0 | ✅ | 운영 환경 강한 랜덤 값 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | 0 | ✅ | 기본 30 |
| `JWT_REFRESH_EXPIRE_DAYS` | 0 | ✅ | refresh token 만료 |
| `SMTP_HOST` | 0/1 | ✅ | `smtp.gmail.com` |
| `SMTP_PORT` | 0/1 | ✅ | `587` |
| `SMTP_USERNAME` | 0/1 | ✅ | `deundeun.dcsw@gmail.com` |
| `SMTP_PASSWORD` | 0/1 | ✅ | Gmail 앱 비밀번호 |
| `SMTP_FROM` | 0/1 | ✅ | `deundeun.dcsw@gmail.com` |
| `SMTP_USE_TLS` | 0/1 | ✅ | `true` (587 포트) |
| `FILE_STORAGE_*` | 3 | — | **미사용** (D-BE-006 이미지 비저장) |
| `ANALYSIS_SERVER_BASE_URL` | 4 | ✅ | 외부 AI 분석 서버 |
| `ANALYSIS_SERVER_API_KEY` | 4 | ✅ | |
| `ANALYSIS_CALLBACK_SECRET` | 4 | ✅ | callback 서명 검증 |
| `DOCKERHUB_USERNAME` / `TOKEN` | CD | — | CI/CD 이미지 push |

---

## 15. 관련 문서

| 문서 | 용도 |
|------|------|
| [development-environment.md](./development-environment.md) | Python·의존성·CI/CD·버전 |
| [architecture.md](./architecture.md) | 레이어·도메인 역할 |
| [implementation-status.md](./implementation-status.md) | 구현 현황 정본 — Phase별 완료/미구현 |
| [ocr-checkup-design.md](./ocr-checkup-design.md) | OCR 설계 — **구현 완료** (동기 미리보기 방식으로 일부 변형) |
| [요구사항정의서](./든든_건강미션앱_요구사항정의서_개발설계서_v0.1%20.md) | FR·화면·테스트 케이스 원본 |

---

## 16. 다음 액션

1. **Phase 0** — `docker/docker-compose.yml`(postgres) + Alembic 초기화 + `SmtpEmailClient` + `get_current_user`
2. **Phase 1** — Auth API 전체 구현 (SMTP 인증 메일 발송 연동)
3. 각 Phase 완료 시 `implementation-status.md` 체크리스트 갱신
4. GitHub 이슈 등록: [docs/issues/](./issues/) 또는 `.github/ISSUE_TEMPLATE/phase-*.yml`

Phase 1부터 개발을 시작할 때 이 문서의 해당 섹션을 기준으로 상세 스키마·에러 코드·테스트를 확정한다.
