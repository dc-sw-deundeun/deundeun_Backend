# deundeun Backend 구현 현황

> 마지막 업데이트: 2026-06-23
> 상태: OCR 검진표 업로드/처리 플로우 구현 완료, 나머지 도메인은 단계별 구현 예정

## 1. 완료된 작업

### CI/CD

- GitHub Actions CI (`ruff` + `pytest` + Docker build)
- CD develop/main (Docker Hub push + VM 배포 스켈레톤)

### FastAPI 앱 스캐폴딩

- Layered Architecture (Router -> Service -> Repository -> DB)
- `GET /health` 동작
- 전역 `ApiResponse` 포맷, exception handler
- 외부 분석 서버 연동 구조 리팩터

### OCR 검진표 업로드/처리

- `POST /api/v1/records/checkups/upload`
  - jpg/png 매직넘버 검증, 미지원 포맷은 415 `UNSUPPORTED_MEDIA_TYPE`
  - 사용자별 `file_hash` 중복 업로드 방어
  - `LocalFileStorage`에 원본 이미지를 임시 저장
  - `CheckupRecord`와 `OcrJob` 생성 후 FastAPI `BackgroundTasks`로 OCR 즉시 실행
- Clova OCR 연동
  - 로컬 이미지를 외부 URL로 노출하지 않고 base64 `data`로 전송
  - `OcrClient.recognize(image: bytes, image_format: str)` 인터페이스로 교체 가능
- OCR 처리 수명주기
  - `claim_job`/`process_single`로 특정 job을 `PENDING -> PROCESSING` 전환 후 처리
  - 성공 시 metric을 저장하고 원본 이미지를 커밋 이후 best-effort 삭제
  - 실패 시 job/record를 FAILED로 남기고 원본 이미지는 재처리를 위해 보존
  - raw OCR JSON 저장과 `raw_result_url` 컬럼 제거 마이그레이션 추가
- 검수/수정 API
  - OCR metric 조회, 단건 수정, 일괄 수정, 검수 완료
  - OCR 완료 전 검수 차단
  - 검수 완료 전 분석 차단 게이트
- OCR 재처리
  - `POST /api/v1/ocr/checkups/{record_id}/reprocess`
  - 원본 이미지가 없으면 409 `IMAGE_UNAVAILABLE`
  - 원본 이미지가 있으면 검수 상태 초기화, 새 job 생성, 백그라운드 처리 트리거
- 복구 배치
  - APScheduler가 lifespan에서 시작/종료
  - `run_ocr_batch`가 stuck `PROCESSING` job 회수와 남은 `PENDING` job 처리를 담당

### 도메인 현황

| 도메인 | 상태 | 비고 |
|--------|------|------|
| record | partial | OCR 검진표 업로드/metric 수정/검수/삭제 구현 |
| ocr | implemented | Clova base64 입력, job 상태 조회, 재처리, 복구 배치 구현 |
| analysis | partial | 검수 완료 전 분석 차단 게이트 구현, 외부 분석 본처리는 stub |
| auth | stub | Phase 1 예정 |
| user | stub | Phase 1 예정 |
| onboarding | stub | Phase 2 예정 |
| health_metric | stub | 항목 기준·설명 |
| mission | stub | Phase 4 예정 |
| character | stub | Phase 4 예정 |
| home | stub | Phase 5 예정 |
| notification | stub | Phase 6 예정 |
| support | stub | Phase 7 예정 |

### Infrastructure

| Client | 경로 | 상태 | 역할 |
|--------|------|------|------|
| FileStorage | `infrastructure/storage/` | implemented | 로컬 임시 저장, read/exists/delete |
| ClovaOcrClient | `infrastructure/ocr/` | implemented | Clova General OCR 호출 |
| AnalysisClient | `infrastructure/external_analysis/` | stub | 외부 AI 분석 서버 호출 |
| EmailClient | `infrastructure/email/` | stub | 이메일 발송 |
| PushClient | `infrastructure/push/` | stub | 푸시 알림 |
| WearableClient | `infrastructure/wearable/` | stub | 웨어러블 연동 |

### Workers

| Worker | 상태 | 역할 |
|--------|------|------|
| ocr_worker | implemented | pending/stuck OCR job 복구 처리 |
| scheduler | implemented | APScheduler로 OCR 복구 배치 주기 실행 |
| analysis_result_worker | stub | callback + polling 결과 수신 |
| wearable_sync_worker | stub | 웨어러블 데이터 동기화 |
| mission_notification_worker | stub | 미션 알림 |
| record_reminder_worker | stub | 검진 등록 주기 알림 |

## 2. API 현황 (/docs 기준)

### Record API

- `POST /api/v1/records/checkups/upload` - 구현
- `GET /api/v1/records/checkups/{record_id}/metrics` - 구현
- `PATCH /api/v1/records/checkups/{record_id}/metrics/{metric_id}` - 구현
- `PUT /api/v1/records/checkups/{record_id}/metrics` - 구현
- `POST /api/v1/records/checkups/{record_id}/verify` - 구현
- `DELETE /api/v1/records/checkups/{record_id}` - 구현
- `GET /api/v1/records/checkups` - 미구현
- `GET /api/v1/records/checkups/{record_id}` - 미구현
- `POST /api/v1/records/meals` - 미구현
- `GET /api/v1/records/meals` - 미구현

### OCR API

- `GET /api/v1/ocr/jobs/{job_id}` - 구현
- `POST /api/v1/ocr/checkups/{record_id}/reprocess` - 구현

### Analysis API

- `POST /api/v1/analysis/checkups/{record_id}` - 검수 완료 게이트 구현, 외부 분석 본처리 미구현
- `GET /api/v1/analysis/jobs/{analysis_job_id}` - 미구현
- `GET /api/v1/analysis/jobs/{analysis_job_id}/result` - 미구현
- `POST /api/v1/analysis/callback` - 미구현

### 기타 API

- Auth, Onboarding, Home, Mission, Character, My, Notification - README API 목록 참고

## 3. 검진표 OCR 흐름

```
Frontend
  -> POST /api/v1/records/checkups/upload
FastAPI
  -> jpg/png 포맷 검증, file_hash 중복 확인
  -> LocalFileStorage 임시 저장
  -> CheckupRecord + OcrJob(PENDING) 생성 후 commit
  -> BackgroundTasks로 process_single(job_id) 실행
OCR Service
  -> job claim(PENDING -> PROCESSING)
  -> LocalFileStorage.read(file_url)
  -> Clova OCR base64 data 호출
  -> 파싱 결과 CheckupMetricResult 저장
  -> OcrJob(COMPLETED), record.ocr_status=COMPLETED commit
  -> 원본 이미지 best-effort 삭제
Frontend
  -> metric 조회/수정
  -> 검수 완료 후 분석 요청 가능
```

실패한 OCR job은 FAILED로 남고 원본 이미지는 보존됩니다. 사용자는 원본 이미지가 남아 있는 경우 `/api/v1/ocr/checkups/{record_id}/reprocess`로 재처리할 수 있습니다.

## 4. 미구현 / 다음 단계

| Phase | 내용 | 선행 조건 |
|-------|------|-----------|
| 1 | Auth + User (JWT) | DB 확정 |
| 2 | Onboarding + Wearable | Phase 1 |
| 3 | 외부 AnalysisClient 실연동 | 검수 완료 record |
| 3 | Record 목록/상세 API 완성 | OCR record 스키마 |
| 4 | Mission + Character | Phase 3 |
| 5 | Home Aggregation | Phase 4 |
| 6 | Notification + Workers | Phase 5 |
| 7 | My + Support | Phase 6 |

## 5. 환경 설정 체크리스트

- [x] `alembic init` 및 OCR/checkup 스키마 migration
- [x] `ocr_jobs.raw_result_url` 제거 migration
- [x] `python-multipart` 런타임 의존성
- [x] `apscheduler==3.10.4` 런타임 의존성
- [ ] `DATABASE_URL` 운영값 설정 (PostgreSQL)
- [ ] `JWT_SECRET_KEY`
- [ ] `DOCKERHUB_USERNAME` / `DOCKERHUB_TOKEN` (CI/CD)
- [ ] `ANALYSIS_SERVER_BASE_URL` (Phase 3)
- [ ] `ANALYSIS_SERVER_API_KEY` (Phase 3)
- [ ] `ANALYSIS_CALLBACK_SECRET` (Phase 3)
- [ ] `CLOVA_OCR_INVOKE_URL`
- [ ] `CLOVA_OCR_SECRET_KEY`
- [ ] `LOCAL_STORAGE_DIR` 운영 경로 지정 및 볼륨/권한 확인
