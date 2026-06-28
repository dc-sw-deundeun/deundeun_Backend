# 개발 환경

> 기준일: 2026-06-29  
> 이 문서는 로컬 개발, 테스트, CI가 어떤 환경을 기준으로 도는지 정리합니다.

## 런타임

| 항목 | 기준 |
|------|------|
| Python | 3.12.6 (`.python-version`) |
| Docker image | `python:3.12-slim` |
| CI Python | 3.12.6 (`.github/workflows/ci.yml`) |
| 패키지 관리 | `requirements.txt`, `requirements-dev.txt` |
| DB | PostgreSQL 16 |

로컬 기본 Python이 3.9여도, 프로젝트 테스트와 CI 기준은 Python 3.12입니다. 로컬에서는 `.venv`를 3.12로 만들어 쓰는 것을 권장합니다.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

## 로컬 실행

```bash
cp .env.example .env
docker compose -f docker/docker-compose.yml up -d postgres
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

로컬 compose Postgres는 기본적으로 호스트 `127.0.0.1:55432`에 바인딩됩니다.

```bash
DATABASE_URL=postgresql+psycopg2://deundeun:deundeun@localhost:55432/deundeun
```

## 테스트와 검사

CI와 같은 순서로 확인하려면 아래를 실행합니다.

```bash
ruff check .
ruff format --check .
mypy app tests
alembic upgrade head
pytest tests/
docker build -t deundeun/backend:ci-check .
```

CI는 pull request와 `develop`, `main` push에서 실행됩니다.

| Job | 내용 |
|-----|------|
| Lint | `ruff check`, `ruff format --check`, `mypy app tests` |
| Test | PostgreSQL service + `alembic upgrade head` + `pytest tests/` |
| Docker Build | Docker image build 검증, push 없음 |

## 주요 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| FastAPI | 0.115.5 | API framework |
| SQLAlchemy | 2.0.36 | ORM |
| Alembic | 1.14.0 | migration |
| pydantic-settings | 2.6.1 | env 설정 |
| python-jose | 3.5.0 | JWT |
| httpx | 0.27.2 | 외부 HTTP client |
| psycopg2-binary | 2.9.10 | PostgreSQL driver |
| pytest | 8.3.4 | test |
| ruff | 0.8.4 | lint/format |
| mypy | 1.13.0 | type check |

## 환경 변수 파일

| 파일 | 용도 | Git |
|------|------|-----|
| `.env.example` | 로컬 개발 템플릿 | 추적 |
| `.env.server.example` | 서버 `/opt/deundeun/.env` 템플릿 | 추적 |
| `.env` | 로컬 실제 값 | ignore |
| `.env.server` | 로컬 서버값 보관용 | ignore |
| `/opt/deundeun/.env` | 서버 실제 값 | repo 밖 |

실제 secret은 예시 파일에 넣지 않습니다. 서버 배포 값은 [deployment-onprem.md](./deployment-onprem.md)를 따릅니다.

## CORS와 프론트엔드

웹 프론트엔드는 백엔드 `.env`의 `CORS_ALLOW_ORIGINS`에 origin이 있어야 브라우저 요청이 통과합니다.

```bash
CORS_ALLOW_ORIGINS=["http://localhost:3000","http://localhost:5173"]
```

스테이징 서버는 현재 `https://www.deundeun.xyz`, `http://localhost:5173`, `http://localhost:3000`을 허용하도록 설정했습니다.

## 관련 문서

- [implementation-status.md](./implementation-status.md)
- [deployment-onprem.md](./deployment-onprem.md)
- [architecture.md](./architecture.md)
