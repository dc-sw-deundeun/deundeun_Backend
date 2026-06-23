# OCR 요청 즉시 실행 + 로컬 임시 저장 설계

- 날짜: 2026-06-23
- 대상 브랜치: feat/#6/건강검진표-이미지-업로드촬영-기반-ocr-분석-및-수치-자동-반영-api-구현
- 관련 PR: #8

## 배경 / 문제

현재 OCR 파이프라인 로직(`OcrService.process_job` / `process_pending`, 파서, Clova 클라이언트)은
구현·테스트되어 있으나, 실제로 동작하지 않는 두 가지 운영 공백이 있다.

1. **트리거 부재**: `process_pending`을 호출하는 주체가 테스트뿐이다.
   `scheduler.start_scheduler()`는 `NotImplementedError`이고 `lifespan`에서 호출되지도 않는다.
   따라서 업로드된 모든 검진표는 `PENDING`에 영원히 머문다.
2. **스토리지가 stub 고정**: `get_file_storage`/`get_ocr_service`/`get_record_service`가
   무조건 `StubFileStorage()`를 쓴다. 업로드 파일이 실제로 저장되지 않고 `file_url`에는
   `s3://stub/...` 가짜 값이 들어간다. Clova가 그 URL로 이미지를 가져갈 수 없다.

## 목표 (이번 스펙의 범위)

- 업로드 **요청 시 즉시** OCR을 백그라운드로 실행한다(정상 경로).
- 사진을 **로컬에 임시 저장**한다(S3 미사용). OCR **성공 시 즉시 삭제**한다.
- Clova OCR에 이미지를 **base64 `data`**로 전송한다(로컬 파일은 외부 URL로 접근 불가).
- 배치는 **복구 전용**으로 동작한다: 프로세스 재시작 등으로 트리거가 유실된 `PENDING` 잡과
  크래시로 멈춘 `PROCESSING` 잡을 처리한다.
- jpg / jpeg / png를 지원한다(카메라 직촬영 대응).

## 비목표 (이번 스펙 밖)

- S3 등 영구 객체 스토리지 연동.
- Celery/RQ 등 외부 작업 큐, 멀티 인스턴스 분산 처리.
- raw OCR 응답(JSON)의 영구 보관/감사 로그.
- 멀티 인스턴스 동시성을 위한 `SELECT ... FOR UPDATE SKIP LOCKED`(단일 인스턴스 전제 유지).

## 결정 사항 요약

| # | 항목 | 결정 |
|---|---|---|
| 1 | 트리거 모델 | FastAPI `BackgroundTasks` + 202 응답 + `GET /jobs/{id}` 폴링 |
| 2 | 이미지 수명 | OCR 성공 시 즉시 삭제. FAILED/미완료는 보존(재처리용) |
| 3 | 스토리지 | `LocalFileStorage`(upload/read/exists/delete), `get_file_storage` 단일 소스 |
| 4 | Clova 입력 | `recognize(image: bytes, image_format)` → base64 `data` 전송 |
| 5 | 포맷 판별 | 매직넘버로 jpg/jpeg/png 판별 (JPEG `FF D8 FF`, PNG `89 50 4E 47`) |
| 6 | reprocess | 원본 이미지가 있을 때만 허용. 없으면 409 `IMAGE_UNAVAILABLE` |
| 7 | stuck 처리 | PROCESSING 타임아웃 → FAILED(현행). 수동 reprocess로 재시도 |
| 8 | raw JSON | 디스크 저장 폐지. `raw_result_url`/`_store_raw`/`_discard_raw` 제거 |
| 9 | 배치 | 스케줄러(APScheduler)로 `run_ocr_batch`를 주기 실행(복구 전용) |

## 아키텍처 / 제어 흐름

### 정상 경로 (요청 시)

```
POST /checkups/upload
  content = await file.read()
  image_format = detect_format(content)        # jpg|jpeg|png, 아니면 415
  file_hash = sha256(content)
  dedup: find_by_user_and_hash → 있으면 200(기존 record_id, ocr_job_id=0)
  file_url(key) = await storage.upload(f"checkups/{user}/{hash}.{ext}", content)
  record(PENDING) + job(PENDING) → commit
  background_tasks.add_task(run_ocr_job, job_id)
  → 202 { record_id, ocr_job_id }

run_ocr_job(job_id)   # 응답 후 실행, 독립 DB 세션
  with SessionLocal() as db:
    service = build_ocr_service(db)
    await service.process_single(job_id)
```

### process_single(job_id)

```
job = claim(job_id)        # PENDING→PROCESSING 원자 전환 + commit
if job is None: return     # 이미 배치/다른 트리거가 점유 → skip
image = await storage.read(record.file_url)
result = await ocr_client.recognize(image, image_format=...)   # 재시도 포함
with begin_nested():
    parsed = parser.parse(result)
    upsert_ocr_metrics(...)
    mark_completed(job)
    set_ocr_status(record, COMPLETED)
commit()
await storage.delete(record.file_url)   # 성공 시에만, best-effort(커밋 후)
```

실패/예외 경로는 기존 `process_job`과 동일하게 `mark_failed` + 상태 FAILED. 이미지는 보존한다.

### 복구 경로 (배치)

```
lifespan 시작 → start_scheduler()
  AsyncIOScheduler.add_job(run_ocr_batch, interval=ocr_polling_interval_seconds, max_instances=1)
lifespan 종료 → stop_scheduler()

run_ocr_batch
  recover_stuck()      # PROCESSING & requested_at < now-timeout → FAILED (+ commit)
  process_pending()    # 남은 PENDING을 claim_next_pending 루프로 처리
```

`process_single`과 `process_pending` 모두 `claim`(PENDING→PROCESSING 원자 전환 후 commit)을
선행하므로, 요청 트리거와 배치가 같은 잡을 중복 처리하지 않는다.

## 컴포넌트별 변경

### `app/infrastructure/storage/file_storage.py`
- `FileStorage` Protocol: 기존 `upload(key, content) -> str`, `delete(key) -> None` 유지,
  `read(key) -> bytes`, `exists(key) -> bool` 추가.
- `LocalFileStorage`: `base_dir`(설정값) 하위에 key 경로로 저장. `upload`는 상위 디렉터리 생성 후 기록,
  `read`는 바이트 반환(없으면 `FileNotFoundError`), `exists`는 파일 존재 여부 반환,
  `delete`는 파일 제거(없으면 무시).
- `StubFileStorage`: 테스트용. `read`/`exists` 포함.

### `app/infrastructure/ocr/format.py` (신규)
- `detect_image_format(content: bytes) -> str | None`: 매직넘버로 `"jpg"`/`"png"` 판별
  (jpeg는 jpg로 매핑). 미지원이면 `None`.

### `app/infrastructure/ocr/clova_client.py` / `ocr_client.py`
- `OcrClient` Protocol: `recognize(self, image: bytes, image_format: str) -> OcrResultDTO`.
- `ClovaOcrClient`: payload를 `images[{format, name, data: base64(image)}]`로 전송.
- `StubOcrClient`: 시그니처 일치, 고정 결과 반환.

### `app/domains/ocr/service.py`
- `process_single(job_id)` 추가: 특정 잡 claim 후 `process_job` 로직 수행.
- `process_job`: `recognize`에 URL 대신 바이트 전달(`storage.read` 후), 성공 시 `storage.delete`.
- raw 관련 제거: `_store_raw`/`_discard_raw`, `mark_completed`의 `raw_result_url` 인자.

### `app/domains/ocr/repository.py`
- `claim_job(job_id)` 추가: `status=PENDING`인 해당 잡만 `PROCESSING`으로 전환(아니면 None).
- `mark_completed` 시그니처에서 `raw_result_url` 제거.

### `app/domains/ocr/models.py` + alembic
- `OcrJob.raw_result_url` 컬럼 제거 → 신규 alembic 마이그레이션 추가(downgrade 포함).

### `app/api/v1/record_router.py`
- `upload_checkup`: 포맷 판별(미지원 415), `storage.upload`, 업로드 후 `background_tasks.add_task`.
  커밋 실패 시 기존 `_safe_delete` 보상 유지.
- `BackgroundTasks` 파라미터 주입, `get_ocr_job_runner`로 독립 세션 기반 job runner 주입.

### `app/api/v1/ocr_router.py`
- `reprocess`: 원본 이미지 존재 확인. 없으면 409 `IMAGE_UNAVAILABLE`. 허용 시 background 트리거.

### `app/domains/ocr/dependencies.py`
- `get_file_storage()` → `LocalFileStorage(settings.local_storage_dir)`.
- `get_ocr_service`/`get_record_service`의 하드코딩 `StubFileStorage()` → `get_file_storage()` 통일.
- 백그라운드용 세션/서비스 빌더(요청 스코프 밖에서 사용) 제공.

### `app/workers/scheduler.py` + `app/main.py`
- `start_scheduler()`: `AsyncIOScheduler`로 `run_ocr_batch` 주기 등록(`max_instances=1`,
  매 실행마다 새 세션). `stop_scheduler()`: 종료.
- `main.lifespan`: 시작 시 `start_scheduler()`, 종료 시 `stop_scheduler()` 호출.

### `app/core/config.py`
- `local_storage_dir: str = "var/ocr_tmp"` 추가.

## 에러 처리

- 미지원 포맷 업로드 → 415(`UNSUPPORTED_MEDIA_TYPE`).
- OCR 인식 실패(재시도 소진) → 잡 FAILED, 이미지 보존, `/reprocess`로 재시도 가능.
- 백그라운드 태스크 실행 전 프로세스 재시작 → 잡 PENDING 잔존 → 다음 배치가 처리.
- 백그라운드 OCR 도중 크래시 → 잡 PROCESSING 잔존 → 배치 `recover_stuck`이 FAILED 처리.
- 이미지 없는 기록 reprocess → 409 `IMAGE_UNAVAILABLE`.
- 스토리지 delete 실패 → best-effort 무시(로그).

## 동시성 / 원자성

- `claim`(PENDING→PROCESSING + commit)으로 요청 트리거와 배치의 중복 점유 차단.
- DB 결과는 `begin_nested` SAVEPOINT로 묶고 외부 부수효과(이미지 삭제)는 **커밋 성공 이후** 수행.
- 단일 인스턴스 전제. 멀티 인스턴스는 비목표(추후 `SKIP LOCKED`).

## 테스트 계획

- `LocalFileStorage`: upload→read 왕복, delete 후 read가 FileNotFoundError, 없는 파일 delete 무시.
- `detect_image_format`: jpg/jpeg/png 매직넘버 → 정확한 포맷, 기타 → None.
- `ClovaOcrClient`: payload에 base64 `data`와 올바른 `format` 포함, URL 미포함.
- `process_single`: claim 성공 시 처리·이미지 삭제, 이미 점유면 skip.
- 업로드 엔드포인트: 202 + background 트리거 등록(태스크 캡처), 미지원 포맷 415, dedup 200.
- reprocess: 이미지 있으면 트리거, 없으면 409.
- 스케줄러: `run_ocr_batch`가 PENDING/stuck을 복구하는지(기존 worker 테스트 유지/보강).
- 제거: raw 저장/보상 관련 테스트, URL 기반 recognize 테스트 → 바이트 기반으로 갱신.

## 마이그레이션 / 호환성

- `OcrJob.raw_result_url` 제거 마이그레이션. 기존 데이터의 해당 컬럼 값은 폐기(비목표).
- `var/ocr_tmp`는 런타임 생성. `.gitignore`에 추가.
- 기존 `FileStorage.upload` 명칭은 유지하고 `read`/`exists`만 추가해 호출부 변경을 줄인다.
