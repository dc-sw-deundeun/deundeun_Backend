# 아키텍처

> 기준일: 2026-06-29  
> 현재 백엔드는 FastAPI API 서버이며, 검진 OCR·기록·인증·온보딩 일부를 구현했습니다.

## 전체 구조

```text
Frontend / Mobile App
  -> FastAPI (/api/v1)
  -> PostgreSQL
  -> External services
       - SMTP
       - Clova OCR
       - External Analysis Server (후속 구현)
```

FastAPI는 검진 AI 분석 모델을 직접 들고 있지 않습니다. 분석 요청, 상태 관리, 결과 저장은 `analysis` 도메인이 맡고, 실제 분석은 외부 분석 서버로 위임하는 구조입니다. 현재 `analysis` 라우터와 클라이언트는 스캐폴딩/stub 상태입니다.

## 레이어 규칙

```text
Router -> Service -> Repository -> DB
             |
             -> Infrastructure client
```

| 레이어 | 경로 | 역할 |
|--------|------|------|
| Router | `app/api/v1/` | URL, DTO 검증, 인증 의존성, 응답 반환 |
| Service | `app/domains/*/service.py` | 비즈니스 흐름 조율 |
| Repository | `app/domains/*/repository.py` | DB 조회·저장 |
| Policy | `app/domains/*/policy.py` | 도메인 규칙, 권한, 상태 전이 |
| Infrastructure | `app/infrastructure/` | SMTP, OCR, 외부 분석, wearable 등 외부 연동 |
| Worker | `app/workers/` | polling, 알림, 동기화 같은 백그라운드 작업 |

Router에는 비즈니스 로직을 넣지 않습니다. Service는 DB 세부 쿼리를 직접 흩뿌리지 않고 Repository를 통합니다.

## 주요 도메인

| 도메인 | 상태 | 설명 |
|--------|------|------|
| `auth`, `user` | 구현 | 이메일 인증, 회원가입, 로그인, refresh/logout, 약관 동의 |
| `onboarding` | 구현 | 상태 조회, wearable connect/skip, 완료 처리 |
| `record` | 구현 | 검진 업로드, OCR preview, commit, metric 수정, verify, 목록/상세/trend |
| `ocr` | 구현 | Clova OCR job, parser, metric dictionary |
| `health_metric` | 구현 | 건강 지표 평가, reference seed |
| `analysis` | 부분 | 모델·repository 일부 존재, API는 stub |
| `mission`, `character`, `home`, `notification`, `my` | stub | 후속 phase |

상세 API 상태는 [implementation-status.md](./implementation-status.md)를 기준으로 봅니다.

## API 구성

모든 서비스 API는 `/api/v1` 아래에 있습니다.

```text
/api/v1/auth
/api/v1/onboarding
/api/v1/records
/api/v1/ocr
/api/v1/health-metrics
/api/v1/analysis       # stub
/api/v1/missions       # stub
/api/v1/characters     # stub
/api/v1/home           # stub
/api/v1/notifications  # stub
/api/v1/my             # stub
```

공통 응답 envelope:

```json
{
  "success": true,
  "message": "요청이 성공했습니다.",
  "data": {},
  "error_code": null
}
```

## 배포 구조

스테이징은 `develop` 브랜치 기준으로 배포합니다.

```text
develop push
  -> CI
  -> Docker image push (:develop, :sha-xxxxxxx)
  -> SSH deploy
  -> docker compose: postgres + api + nginx
```

온프레미스 배포 상세는 [deployment-onprem.md](./deployment-onprem.md)에 둡니다.

## 서버 구성

```text
Client
  -> api.deundeun.xyz:80
  -> compose nginx
  -> api:8000
  -> postgres:5432
```

현재 HTTPS는 아직 구성하지 않았습니다. HTTPS 웹 프론트엔드에서 호출하려면 API도 HTTPS를 적용해야 브라우저 mixed content에 걸리지 않습니다.

## 설정 파일

| 파일 | 역할 |
|------|------|
| `app/core/config.py` | 애플리케이션 설정 |
| `app/core/cors.py` | CORS origin 파싱·미들웨어 구성 |
| `.env.example` | 로컬 개발 템플릿 |
| `.env.server.example` | 서버 `/opt/deundeun/.env` 템플릿 |
| `docker/docker-compose.yml` | postgres, api, nginx compose |
| `docker/nginx/templates/api.conf.template` | nginx reverse proxy template |
| `scripts/deploy.sh` | 서버 배포 스크립트 |
