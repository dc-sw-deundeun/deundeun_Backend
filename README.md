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
# 의존성 설치
pip install -r requirements-dev.txt

# 환경변수 설정
cp .env.example .env
# .env 파일에서 필요한 값 수정

# 서버 실행
uvicorn app.main:app --reload

# API 문서 확인
open http://localhost:8000/docs

# 테스트
pytest tests/

# 린트
ruff check .
```

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

- Docker Hub에 `:develop`, `:sha-<short>` 태그로 push
- `ENABLE_STAGING_DEPLOY=true` variable 설정 시 VM에 `scripts/deploy.sh` 실행

### CD — 프로덕션 (`deploy-production.yml`)

`main` 브랜치 CI 통과 후 자동 실행됩니다.

- Docker Hub에 `:latest`, `:prod-sha-<short>` 태그로 push
- `ENABLE_PRODUCTION_DEPLOY=true` variable 설정 시 VM에 배포

---

## GitHub Secrets 설정

**Settings → Secrets and variables → Actions → Repository secrets** 에 등록합니다.

| Secret | 용도 | 등록 시점 |
|--------|------|-----------|
| `DOCKERHUB_USERNAME` | Docker Hub 로그인 ID | 즉시 필요 |
| `DOCKERHUB_TOKEN` | Docker Hub Access Token | 즉시 필요 |
| `GCP_VM_HOST` | 스테이징 VM IP / hostname | VM 준비 후 |
| `GCP_VM_USER` | SSH 사용자 (예: `deploy`) | VM 준비 후 |
| `GCP_VM_SSH_KEY` | 배포용 SSH private key | VM 준비 후 |
| `GCP_VM_HOST_PROD` | 프로덕션 VM IP / hostname | main 배포 시 |

> `DOCKERHUB_TOKEN`은 Docker Hub **Access Token**을 사용하세요 (계정 비밀번호 대신).  
> 발급 경로: Docker Hub → Account Settings → Security → Access Tokens

## GitHub Variables 설정 (배포 on/off)

**Settings → Secrets and variables → Actions → Variables** 탭에서 등록합니다.

| Variable | 값 | 설명 |
|----------|-----|------|
| `ENABLE_STAGING_DEPLOY` | `true` | 스테이징 VM 배포 job 활성화 (미설정 시 skip) |
| `ENABLE_PRODUCTION_DEPLOY` | `true` | 프로덕션 VM 배포 job 활성화 (미설정 시 skip) |

> GitHub Actions에서는 `secrets`를 job `if` 조건에서 직접 참조할 수 없습니다.  
> VM secret 등록 + 위 variable을 `true`로 설정해야 배포 job이 실행됩니다.

---

## GCP VM 사전 준비 사항

VM에 아래 작업이 완료되어야 배포 스크립트가 동작합니다.

1. Docker Engine 설치
2. 배포 스크립트 복사: `scp scripts/deploy.sh user@VM:/opt/deundeun/deploy.sh`
3. 환경변수 파일 배치: `/opt/deundeun/.env`
4. 방화벽 8000 포트 허용 (또는 Nginx reverse proxy 설정)
5. SSH public key 등록 (배포 전용 키 권장)

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

# docker-compose (단일 파일, VM/API 배포 profile)
IMAGE_TAG=deundeun/backend:latest ENV_FILE=/opt/deundeun/.env \
  docker compose -f docker/docker-compose.yml --profile deploy up -d api
```
