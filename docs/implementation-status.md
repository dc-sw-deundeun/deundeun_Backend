# deundeun Backend 구현 현황

> 마지막 업데이트: 2026-06-17
> 상태: Phase 0.5 스캐폴딩 (비즈니스 로직 미구현)

## 1. 완료된 작업

### CI/CD

- GitHub Actions CI (`ruff` + `pytest` + Docker build)
- CD develop/main (Docker Hub push + VM 배포 스켈레톤)

### FastAPI 앱 스캐폴딩

- Layered Architecture (Router → Service → Repository → DB)
- `GET /health` 동작
- 전역 `ApiResponse` 포맷, exception handler
- 외부 분석 서버 연동 구조 리팩터 (Phase 0.5)

### 도메인 (stub)

| 도메인 | 상태 | 비고 |
|--------|------|------|
| auth | stub | Phase 1 예정 |
| user | stub | Phase 1 예정 |
| onboarding | stub | Phase 2 예정 |
| record | stub (리팩터 완료) | upload/metrics 중심, analyzer 제거 |
| analysis | stub (신규) | 외부 분석 서버 연동 |
| health_metric | stub (신규) | 항목 기준·설명 |
| mission | stub | Phase 4 예정 |
| character | stub | Phase 4 예정 |
| home | stub | Phase 5 예정 |
| notification | stub | Phase 6 예정 |
| support | stub | Phase 7 예정 |

### Infrastructure (stub)

| Client | 경로 | 역할 |
|--------|------|------|
| FileStorage | `infrastructure/storage/` | 검진 결과지 저장 |
| AnalysisClient | `infrastructure/external_analysis/` | 외부 AI 분석 서버 호출 |
| EmailClient | `infrastructure/email/` | 이메일 발송 |
| PushClient | `infrastructure/push/` | 푸시 알림 |
| WearableClient | `infrastructure/wearable/` | 웨어러블 연동 |

### Workers (stub)

| Worker | 역할 |
|--------|------|
| analysis_result_worker | callback + polling 결과 수신 |
| wearable_sync_worker | 웨어러블 데이터 동기화 |
| mission_notification_worker | 미션 알림 |
| record_reminder_worker | 검진 등록 주기 알림 |
| scheduler | 주기 작업 등록 |

## 2. API 현황 (/docs 기준)

모든 비즈니스 API는 현재 **501 Not Implemented** stub입니다.

### Record API

- `POST /api/v1/records/checkups/upload`
- `GET /api/v1/records/checkups`
- `GET /api/v1/records/checkups/{record_id}`
- `GET /api/v1/records/checkups/{record_id}/metrics`
- `DELETE /api/v1/records/checkups/{record_id}`
- `POST /api/v1/records/meals`
- `GET /api/v1/records/meals`

### Analysis API (신규)

- `POST /api/v1/analysis/checkups/{record_id}`
- `GET /api/v1/analysis/jobs/{analysis_job_id}`
- `GET /api/v1/analysis/jobs/{analysis_job_id}/result`
- `POST /api/v1/analysis/callback`

### 기타 API

- Auth, Onboarding, Home, Mission, Character, My, Notification — README API 목록 참고

## 3. 검진 분석 흐름 (설계)

```
Frontend
  ↓ POST /records/checkups/upload
FastAPI (RecordService)
  ↓ FileStorage 저장
  ↓ CheckupRecord 생성
  ↓ AnalysisService.create_analysis_job()
  ↓ AnalysisClient.request_analysis()
External Analysis Server
  ↓ Fine-tuned Model 분석
  ↓ Callback 또는 Polling
FastAPI (결과 저장)
  ↓ CheckupMetricResult, CheckupAnalysisSummary 저장
Frontend (결과 조회)
```

FastAPI는 분석 모델을 직접 보유하지 않습니다.

## 4. 미구현 / 다음 단계

| Phase | 내용 | 선행 조건 |
|-------|------|-----------|
| 1 | Auth + User (JWT) | DB 확정 |
| 2 | Onboarding + Wearable | Phase 1 |
| 3 | Record upload + AnalysisClient 실연동 | DB, Analysis Server URL |
| 3 | Callback vs Polling 최종 결정 | 팀 합의 |
| 4 | Mission + Character | Phase 3 |
| 5 | Home Aggregation | Phase 4 |
| 6 | Notification + Workers | Phase 5 |
| 7 | My + Support | Phase 6 |

## 5. 환경 설정 체크리스트

- [ ] `DATABASE_URL`
- [ ] `JWT_SECRET_KEY`
- [ ] `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` (CI/CD)
- [ ] `ANALYSIS_SERVER_BASE_URL` (Phase 3)
- [ ] `ANALYSIS_SERVER_API_KEY` (Phase 3)
- [ ] `ANALYSIS_CALLBACK_SECRET` (Phase 3)
