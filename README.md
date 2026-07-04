# deundeun Backend

든든 건강미션 앱의 FastAPI 백엔드입니다.

## 빠른 참조

| 항목 | 값 |
|------|-----|
| API prefix | `/api/v1` |
| 인증 | `Authorization: Bearer <access_token>` |
| Swagger | `/docs` |
| ReDoc | `/redoc` |
| Health | `GET /health` |
| 로컬 Base URL | `http://localhost:8000` |
| 스테이징 Base URL | `http://api.deundeun.xyz` |

스테이징 API는 현재 HTTP만 열려 있습니다. HTTPS 웹 프론트엔드에서 호출하려면 API도 HTTPS가 필요합니다.

## 로컬 실행

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

cp .env.example .env
docker compose -f docker/docker-compose.yml up -d postgres

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

Swagger:

```text
http://localhost:8000/docs
```

## 테스트

```bash
ruff check .
ruff format --check .
mypy app tests
pytest tests/
docker build -t deundeun/backend:ci-check .
```

CI는 Python 3.12.6 기준으로 `develop`, `main` push와 PR에서 실행됩니다.

## 프론트엔드 연동

로그인 후 access token을 모든 보호 API에 Bearer token으로 보냅니다.

```http
Authorization: Bearer <access_token>
```

공통 응답 형식:

```json
{
  "success": true,
  "message": "요청이 성공했습니다.",
  "data": {},
  "error_code": null
}
```

웹 프론트엔드는 서버 `.env`의 `CORS_ALLOW_ORIGINS`에 origin이 등록되어야 합니다.

```bash
CORS_ALLOW_ORIGINS=["https://www.deundeun.xyz","http://localhost:5173","http://localhost:3000","http://localhost:8081"]
```

네이티브 앱은 브라우저 CORS 정책의 영향을 받지 않습니다.

## 구현 상태

| 영역 | 상태 |
|------|------|
| Auth / User | 구현 |
| Onboarding | 구현 |
| Record / OCR | 구현 |
| HealthMetric | 구현 |
| Analysis | legacy stub |
| Character / Home | 구현 |
| Mission | 부분 (`GET /missions/today` 구현) |
| My / Search | 구현 |
| PKG | 서버/내부 |
| Notification | stub |

자세한 API 상태는 [docs/implementation-status.md](./docs/implementation-status.md)를 봅니다.

## 배포

스테이징 CD는 `develop` 브랜치 CI 성공 후 동작합니다.

```text
develop push
  -> CI
  -> Docker image push (:develop, :sha-xxxxxxx)
  -> SSH deploy
  -> docker compose: postgres + api + nginx
```

서버 배포 job은 GitHub Repository Variable `ENABLE_STAGING_DEPLOY=true`일 때만 실행됩니다.

온프레미스 서버/CD 설정은 [docs/deployment-onprem.md](./docs/deployment-onprem.md)를 봅니다.

## 문서

| 문서 | 내용 |
|------|------|
| [docs/README.md](./docs/README.md) | 문서 인덱스 |
| [docs/implementation-status.md](./docs/implementation-status.md) | API 구현 현황 |
| [docs/api-my-page.md](./docs/api-my-page.md) | 마이페이지 API |
| [docs/api-search.md](./docs/api-search.md) | 질환 검색 API |
| [docs/development-environment.md](./docs/development-environment.md) | 개발·테스트 환경 |
| [docs/deployment-onprem.md](./docs/deployment-onprem.md) | 온프레미스 배포/CD |
| [docs/architecture.md](./docs/architecture.md) | 백엔드 구조 |

실제 secret이 들어간 `.env`, `.env.server`, `/opt/deundeun/.env`는 커밋하지 않습니다.
