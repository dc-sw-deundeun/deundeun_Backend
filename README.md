# deundeun_BE

deundeun 서비스의 FastAPI 백엔드 저장소입니다.

---

## 아키텍처 구조

FastAPI는 **검진 분석 모델을 직접 보유하지 않습니다.** 별도 AI 분석 서버에 요청을 보내고 결과를 저장·제공하는 중간 서버 역할을 합니다.

```
Frontend
  ↓
FastAPI Backend
  ↓
External Analysis Server
  ↓
Fine-tuned AI Model
```

```
Client Request
  ↓
API Router (app/api/v1/)      — URL 정의·DTO 검증·응답 반환만
  ↓
Service (app/domains/*/service.py)  — 비즈니스 로직
  ↓
Repository (app/domains/*/repository.py)  — DB CRUD
  ↓
DB

외부 연동 시:
Service → Infrastructure Client (app/infrastructure/)
```

### 폴더별 역할

| 폴더 | 역할 |
|------|------|
| `app/core/` | 전체 공통 기능 (config, security, exceptions, response 포맷) |
| `app/database/` | DB 연결·세션 관리 (SQLAlchemy) |
| `app/api/v1/` | API URL 정의 및 라우터 집계 |
| `app/domains/` | 도메인별 비즈니스 로직 (auth, record, analysis, mission 등) |
| `app/infrastructure/` | 외부 서비스 연동 (external_analysis, storage, email, push, wearable) |
| `app/workers/` | 자동 실행 백그라운드 작업 (analysis_result, wearable_sync 등) |
| `tests/` | pytest 기반 테스트 |

### API 엔드포인트 구조

```
/api/v1/auth/*           — 로그인·회원가입·이메일 인증
/api/v1/onboarding/*     — 최초 검진 등록·웨어러블 설정
/api/v1/home/*           — 홈 Aggregation
/api/v1/missions/*       — 오늘의 미션·완료·캘린더
/api/v1/records/*        — 검진 결과지 업로드·기록·항목별 수치
/api/v1/analysis/*       — 분석 요청·상태·결과·callback
/api/v1/ocr/*            — OCR job 상태·재처리
/api/v1/characters/*     — 게임 캐릭터·성장
/api/v1/my/*             — 내 정보·알림 설정·탈퇴
/api/v1/notifications/*  — 알림 조회·설정
```

## DB 후보 비교

| 후보 | 장점 | 단점 | 적합도 |
|------|------|------|--------|
| **PostgreSQL** | JSONB, Alembic 생태계, GCP Cloud SQL 지원 | 로컬에 Docker 필요 | **1순위** |
| **MySQL** | GCP Cloud SQL 지원, 친숙도 | JSON 처리 제한적 | 2순위 |
| **SQLite** | 셋업 제로, CI 가벼움 | 운영 부적합 | 개발/CI 전용 병행 가능 |

DB 확정 후 할 일:
- [ ] `DATABASE_URL` 설정
- [ ] `alembic init` → 첫 migration (users 테이블)
- [ ] CI workflow에 DB service container 추가

---

## 로컬 실행

```bash
# 1. 의존성 설치
pip install -r requirements-dev.txt

# 2. 환경변수 설정
cp .env.example .env
# DATABASE_URL 포트 확인 — Compose 기본은 55432 (5432 아님)
# 로컬 Swagger 테스트 시 SMTP 비우면 StubEmailClient → 인증 코드가 서버 로그에 출력됨

# 3. PostgreSQL 기동 (Docker)
docker compose -f docker/docker-compose.yml up -d postgres

# 4. 마이그레이션
alembic upgrade head

# 5. 서버 실행
uvicorn app.main:app --reload --port 8000

# 6. API 문서 (Swagger UI)
open http://localhost:8000/docs
# ReDoc: http://localhost:8000/redoc

# 테스트
pytest tests/

# 린트
ruff check .
```

### Swagger로 Auth 테스트하기

1. `POST /api/v1/auth/email/verify/request` — 이메일·purpose=`SIGNUP` 입력
2. SMTP 미설정 시 **터미널 로그**에서 `인증 코드 (123456)` 확인
3. `POST /api/v1/auth/email/verify/confirm` — email + code 입력 → `verification_token` 복사
4. `POST /api/v1/auth/signup` — email, password(`Passw0rd!` 형식), nickname, verification_token
5. `POST /api/v1/auth/login` → 응답의 `access_token` 복사
6. Swagger 우측 상단 **Authorize** → `access_token` 붙여넣기 (Bearer 제외)
7. `GET /api/v1/auth/me` 실행

---

## 브랜치 전략

| 브랜치 | 용도 |
|--------|------|
| `feature/*` | 기능 개발 단위 브랜치 |
| `develop` | 스테이징 환경 배포 기준 브랜치 |
| `main` | 프로덕션 릴리스 브랜치 |

**흐름**

```
feature/* → PR → develop  (CI 자동 실행 → 통과 시 스테이징 이미지 push + VM 배포)
develop   → PR → main     (릴리스 준비 완료 시)
main      merge            (prod 이미지 push + 프로덕션 VM 배포)
```

---

## CI/CD 파이프라인

### CI (`ci.yml`)

PR 또는 `develop`/`main` push 시 자동 실행됩니다.

| Job | 내용 |
|-----|------|
| lint | `ruff check .` |
| test | `pytest tests/` |
| build | Docker 이미지 빌드 검증 (push 없음) |

### CD — 스테이징 (`deploy-develop.yml`)

`develop` 브랜치 CI 통과 후 자동 실행됩니다.

- `REGISTRY_IMAGE`에 `:develop`, `:sha-<short>` 태그로 push
- `ENABLE_STAGING_DEPLOY=true` variable 설정 시 SSH 대상 서버에서 `scripts/deploy.sh` 실행

### CD — 프로덕션 (`deploy-production.yml`)

`main` 브랜치 CI 통과 후 자동 실행됩니다.

- `REGISTRY_IMAGE`에 `:latest`, `:prod-sha-<short>` 태그로 push
- `ENABLE_PRODUCTION_DEPLOY=true` variable 설정 시 SSH 대상 서버에 배포

CD는 특정 클라우드에 직접 의존하지 않고, **컨테이너 레지스트리 + SSH 대상 서버 + Docker Compose** 계약으로 동작합니다.
GCP VM, 온프레미스 서버, MSP VM 모두 같은 방식으로 연결할 수 있습니다.

---

## GitHub Secrets 설정

**Settings → Secrets and variables → Actions → Repository secrets** 에 등록합니다.

| Secret | 용도 | 등록 시점 |
|--------|------|-----------|
| `REGISTRY_USERNAME` | 컨테이너 레지스트리 로그인 ID | 즉시 필요 |
| `REGISTRY_TOKEN` | 컨테이너 레지스트리 token/password | 즉시 필요 |
| `DEPLOY_HOST_STAGING` | 스테이징 SSH 대상 IP / hostname | 서버 준비 후 |
| `DEPLOY_HOST_PRODUCTION` | 프로덕션 SSH 대상 IP / hostname | 운영 배포 시 |
| `DEPLOY_PORT` | SSH 포트 (기본 22) | 필요 시 |
| `DEPLOY_PORT_STAGING` | 스테이징 SSH 포트 override | 필요 시 |
| `DEPLOY_PORT_PRODUCTION` | 프로덕션 SSH 포트 override | 필요 시 |
| `DEPLOY_USER` | SSH 사용자 (예: `deploy`) | 서버 준비 후 |
| `DEPLOY_SSH_KEY` | 배포용 SSH private key | 서버 준비 후 |

기존 `DOCKERHUB_USERNAME`/`DOCKERHUB_TOKEN`, `GCP_VM_HOST`/`GCP_VM_HOST_PROD`, `GCP_VM_USER`, `GCP_VM_SSH_KEY`도 fallback으로 지원합니다.

## GitHub Variables 설정 (배포 on/off)

**Settings → Secrets and variables → Actions → Variables** 탭에서 등록합니다.

| Variable | 값 | 설명 |
|----------|-----|------|
| `REGISTRY_HOST` | `docker.io` | 레지스트리 hostname (Docker Hub 기본값) |
| `REGISTRY_IMAGE` | `deundeun/backend` | push/pull할 이미지 이름 |
| `ENABLE_STAGING_DEPLOY` | `true` | 스테이징 VM 배포 job 활성화 (미설정 시 skip) |
| `ENABLE_PRODUCTION_DEPLOY` | `true` | 프로덕션 VM 배포 job 활성화 (미설정 시 skip) |
| `DEPLOY_DIR` | `/opt/deundeun` | 대상 서버 배포 디렉터리 |
| `COMPOSE_FILE` | `/opt/deundeun/docker-compose.yml` | 대상 서버 Compose 파일 경로 |
| `APP_ENV_FILE` | `/opt/deundeun/.env` | 컨테이너에 주입할 앱 env 파일 |
| `DEPLOY_SCRIPT` | `/opt/deundeun/deploy.sh` | 대상 서버 배포 스크립트 경로 |
| `RUN_MIGRATIONS` | `true` | 배포 전 `alembic upgrade head` 실행 여부 |

환경별 override가 필요하면 `STAGING_*`, `PRODUCTION_*` prefix를 붙여 설정합니다.
예: `STAGING_DEPLOY_DIR`, `PRODUCTION_APP_ENV_FILE`, `PRODUCTION_RUN_MIGRATIONS`.
Docker Hub가 아닌 Harbor, GHCR, MSP registry 등을 쓰면 `REGISTRY_IMAGE`는 `registry.example.com/deundeun/backend`처럼 registry host를 포함한 full image name으로 설정합니다.

> GitHub Actions에서는 `secrets`를 job `if` 조건에서 직접 참조할 수 없습니다.
> 서버 secret 등록 + `ENABLE_*_DEPLOY=true` variable 설정이 모두 필요합니다.

---

## SSH 대상 서버 사전 준비 사항

온프레미스, MSP VM, 클라우드 VM 모두 아래 계약을 맞추면 배포 스크립트가 동작합니다.

1. Docker Engine 및 Docker Compose v2 설치
2. 배포 디렉터리 생성: `/opt/deundeun`
3. `scripts/deploy.sh` 복사: `/opt/deundeun/deploy.sh`
4. `docker/docker-compose.yml` 복사: `/opt/deundeun/docker-compose.yml`
5. 환경변수 파일 배치: `/opt/deundeun/.env`
6. 컨테이너 레지스트리가 private이면 대상 서버에서 `docker login` 수행
7. 방화벽 8000 포트 허용 또는 Nginx 등 reverse proxy 연결
8. SSH public key 등록 (배포 전용 키 권장)

### `.env` 주입 방식

- `docker compose --env-file "$APP_ENV_FILE"`: Compose 변수 보간에 사용합니다. 예: `IMAGE_TAG`, `API_HOST_PORT`, `API_CONTAINER_NAME`.
- Compose `api.env_file: ${APP_ENV_FILE:-../.env}`: 동일 파일을 컨테이너 내부 애플리케이션 환경변수로 주입합니다. 예: `DATABASE_URL`, `JWT_SECRET_KEY`, `CLOVA_OCR_SECRET_KEY`.
- FastAPI 설정은 알 수 없는 env를 무시하도록 되어 있어, `.env`에 Compose 전용 변수를 함께 둬도 앱 실행에는 영향이 없습니다.

---

## 로컬 실행

```bash
# 의존성 설치
pip install -r requirements-dev.txt

# 서버 실행 (app/ 구현 후 활성화)
uvicorn app.main:app --reload

# 테스트
pytest tests/

# 린트
ruff check .
```

---

## Docker

```bash
# 이미지 빌드
docker build -t deundeun/backend:local .

# 컨테이너 실행
docker run -p 8000:8000 deundeun/backend:local

# docker-compose (단일 파일, SSH 대상/API 배포 profile)
IMAGE_TAG=deundeun/backend:latest APP_ENV_FILE=/opt/deundeun/.env \
  docker compose -f docker/docker-compose.yml --profile deploy up -d api
```
