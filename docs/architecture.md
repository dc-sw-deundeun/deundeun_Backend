# 아키텍처

> 기준일: 2026-07-06
> 현재 백엔드는 FastAPI API 서버이며, 인증·온보딩·검진/OCR·건강지표·캐릭터 성장·홈 집계·마이페이지 일부·알림함·질환 검색을 구현했습니다.

## 전체 구조

```text
Frontend / Mobile App
  -> FastAPI (/api/v1)
  -> PostgreSQL
  -> External services
       - SMTP
       - Clova OCR
       - OpenAI / medical KG(Neo4j)
       - External Analysis Server (legacy 호환/후속 정리)
```

FastAPI는 검진 AI 분석 모델을 직접 들고 있지 않습니다. 저장형 건강지표 분석은 `health_metric` 도메인이 맡고, legacy `analysis` 라우터는 Phase 4 호환용으로 유지합니다.
개인 지식그래프(PKG)는 앱 PostgreSQL에 스냅샷으로 저장되며, 외부 medical KG(Neo4j)와 물리적으로 분리합니다.

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
| `analysis` | legacy stub | Phase 4 호환용. 신규 프론트는 HealthMetric 사용 |
| `mission` | 부분 | 조회(오늘·날짜별·주간·월간·총계)·complete(EXP 지급)·complete 취소(EXP 회수) 구현. 웨어러블 인증은 후속 |
| `character` | 구현 | 캐릭터 성장 상태와 보유 동물 컬렉션 |
| `home` | 구현 | 사용자·캐릭터·오늘 미션·알림 수 집계 |
| `my` | 부분 | 연동 앱 관리, 알림 설정 구현. 프로필·앱잠금·문의·계정삭제는 stub |
| `search` | 구현 | 의학 KG + AI 기반 질환 검색 |
| `pkg` | 서버/내부 | 미션 엔진용 개인 지식그래프 스냅샷 |
| `notification` | 구현 | 알림함·읽음·HealthMetric/레벨업 트리거. 설정은 `my`의 `/notification-settings` 정본 |

상세 API 상태는 [implementation-status.md](./implementation-status.md)를 기준으로 봅니다.

## API 구성

모든 서비스 API는 `/api/v1` 아래에 있습니다.

```text
/api/v1/auth
/api/v1/onboarding
/api/v1/records
/api/v1/ocr
/api/v1/health-metrics
/api/v1/analysis       # legacy stub
/api/v1/missions       # 조회(today·날짜별·주간·월간·총계)·complete(EXP 지급)·complete 취소(EXP 회수) 구현
/api/v1/characters     # 성장/동물 조회 구현
/api/v1/home           # 홈 집계 구현
/api/v1/my             # 연동 앱·알림 설정 구현, 일부 stub
/api/v1/search         # 질환 검색 구현
/api/v1/pkg            # 서버/내부 PKG 조회
/api/v1/notifications  # 알림함 목록·읽음 처리 (설정은 /my/notification-settings)
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
