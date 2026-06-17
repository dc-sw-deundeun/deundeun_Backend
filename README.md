# deundeun_BE

deundeun 서비스의 FastAPI 백엔드 저장소입니다.

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

# docker-compose (VM 환경)
IMAGE_TAG=deundeun/backend:latest docker compose -f docker/docker-compose.vm.yml up -d
```
