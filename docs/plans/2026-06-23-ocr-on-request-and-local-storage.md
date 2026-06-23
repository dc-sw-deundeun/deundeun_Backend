# OCR 요청 즉시 실행 + 로컬 임시 저장 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 업로드 요청 시 OCR을 백그라운드로 즉시 실행하고, 사진을 로컬에 임시 저장(성공 시 삭제)하며, 배치는 복구 전용으로 동작시킨다.

**Architecture:** FastAPI `BackgroundTasks`로 업로드 직후 특정 잡을 백그라운드 OCR 실행(독립 DB 세션). 이미지는 `LocalFileStorage`에 임시 저장하고 Clova에는 base64 `data`로 전송한다. APScheduler가 주기적으로 `run_ocr_batch`(stuck 회수 + 남은 PENDING 처리)를 돌려 트리거 유실/크래시를 복구한다.

**Tech Stack:** Python 3.12, FastAPI 0.115, SQLAlchemy 2.0, Pydantic v2, httpx, APScheduler, pytest + testcontainers(PostgreSQL 16), Alembic, ruff.

## Global Constraints

- Python 3.12. 의존성은 `requirements.txt`/`requirements-dev.txt`에 핀 버전으로 추가.
- 테스트 DB는 실제 PostgreSQL 16(testcontainers). `db_session` fixture는 매 테스트 스키마 생성/drop.
- 모든 커밋 메시지에 **`Co-Authored-By` 줄을 넣지 않는다**(사용자 지시).
- 커밋 전 `ruff check app/ tests/`가 통과해야 한다.
- 스토리지 인터페이스는 기존 `upload`/`delete` 명을 유지하고 `read`/`exists`만 추가한다(스펙의 `save` 리네임은 순수 명명 편차로 생략 — 동작 동일, 호출부 churn 최소화).
- 단일 인스턴스 전제(멀티 인스턴스/`SKIP LOCKED`는 비목표).
- OCR 성공 시에만 원본 이미지 삭제. FAILED/미완료는 보존.

---

### Task 1: 이미지 포맷 판별 유틸

**Files:**
- Create: `app/infrastructure/ocr/format.py`
- Test: `tests/infrastructure/ocr/test_format.py`

**Interfaces:**
- Produces: `detect_image_format(content: bytes) -> str | None` — `"jpg"` | `"png"` | `None`. JPEG(`FF D8 FF`)와 JPEG 변형(jpeg)은 모두 `"jpg"`로, PNG(`89 50 4E 47 0D 0A 1A 0A`)는 `"png"`로 매핑. 그 외는 `None`.

- [ ] **Step 1: Write the failing test**

```python
# tests/infrastructure/ocr/test_format.py
from app.infrastructure.ocr.format import detect_image_format


def test_detects_png():
    assert detect_image_format(b"\x89PNG\r\n\x1a\n rest") == "png"


def test_detects_jpeg():
    assert detect_image_format(b"\xff\xd8\xff\xe0\x00\x10JFIF") == "jpg"


def test_rejects_unknown():
    assert detect_image_format(b"GIF89a") is None


def test_rejects_empty():
    assert detect_image_format(b"") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/infrastructure/ocr/test_format.py -v`
Expected: FAIL — `ModuleNotFoundError: app.infrastructure.ocr.format`

- [ ] **Step 3: Write minimal implementation**

```python
# app/infrastructure/ocr/format.py
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
_JPEG_MAGIC = b"\xff\xd8\xff"


def detect_image_format(content: bytes) -> str | None:
    """매직넘버로 jpg/png를 판별한다. 미지원 포맷은 None."""
    if content.startswith(_PNG_MAGIC):
        return "png"
    if content.startswith(_JPEG_MAGIC):
        return "jpg"
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/infrastructure/ocr/test_format.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/ocr/format.py tests/infrastructure/ocr/test_format.py
git commit -m "feat(ocr): 이미지 포맷(jpg/png) 매직넘버 판별 유틸 추가"
```

---

### Task 2: LocalFileStorage + FileStorage 인터페이스 확장

**Files:**
- Modify: `app/infrastructure/storage/file_storage.py`
- Modify: `app/core/config.py:21-27` (settings에 `local_storage_dir` 추가)
- Modify: `.gitignore` (런타임 임시 디렉터리 무시)
- Test: `tests/infrastructure/storage/test_local_file_storage.py`
- Create: `tests/infrastructure/storage/__init__.py`

**Interfaces:**
- Produces: `FileStorage` Protocol에 `read(self, file_path: str) -> bytes`, `exists(self, file_path: str) -> bool` 추가(기존 `upload`/`delete` 유지).
- Produces: `LocalFileStorage(base_dir: str)` — `upload(file_path, content) -> str`(상대 key 반환), `read(file_path) -> bytes`(없으면 `FileNotFoundError`), `delete(file_path) -> None`(없으면 무시), `exists(file_path) -> bool`.
- Produces: `StubFileStorage`에 `read`(고정 바이트 `b""` 반환), `exists`(항상 True) 추가.
- Produces: `settings.local_storage_dir: str = "var/ocr_tmp"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/infrastructure/storage/test_local_file_storage.py
import pytest

from app.infrastructure.storage.file_storage import LocalFileStorage


@pytest.mark.asyncio
async def test_upload_then_read_roundtrip(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    key = await storage.upload("checkups/1/abc.png", b"image-bytes")
    assert key == "checkups/1/abc.png"
    assert await storage.read(key) == b"image-bytes"
    assert await storage.exists(key) is True


@pytest.mark.asyncio
async def test_delete_removes_file(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    key = await storage.upload("a/b.png", b"x")
    await storage.delete(key)
    assert await storage.exists(key) is False


@pytest.mark.asyncio
async def test_read_missing_raises(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    with pytest.raises(FileNotFoundError):
        await storage.read("nope.png")


@pytest.mark.asyncio
async def test_delete_missing_is_ignored(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    await storage.delete("nope.png")  # 예외 없이 통과
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/infrastructure/storage/test_local_file_storage.py -v`
Expected: FAIL — `ImportError: cannot import name 'LocalFileStorage'`

- [ ] **Step 3: Write minimal implementation**

`app/infrastructure/storage/file_storage.py` 전체를 다음으로 교체:

```python
from pathlib import Path
from typing import Protocol


class FileStorage(Protocol):
    """파일 저장소 인터페이스입니다. 로컬 임시 저장 → 필요 시 S3 등으로 교체 가능합니다."""

    async def upload(self, file_path: str, content: bytes) -> str:
        """파일을 저장하고 접근 key를 반환합니다."""
        ...

    async def read(self, file_path: str) -> bytes: ...

    async def delete(self, file_path: str) -> None: ...

    async def exists(self, file_path: str) -> bool: ...


class LocalFileStorage:
    """로컬 디스크 임시 저장 구현입니다. base_dir 하위에 key 경로로 저장합니다."""

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir)

    def _full(self, file_path: str) -> Path:
        return self._base / file_path

    async def upload(self, file_path: str, content: bytes) -> str:
        full = self._full(file_path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(content)
        return file_path

    async def read(self, file_path: str) -> bytes:
        return self._full(file_path).read_bytes()

    async def delete(self, file_path: str) -> None:
        self._full(file_path).unlink(missing_ok=True)

    async def exists(self, file_path: str) -> bool:
        return self._full(file_path).is_file()


class StubFileStorage:
    """개발/테스트용 stub 구현입니다."""

    async def upload(self, file_path: str, content: bytes) -> str:
        return file_path

    async def read(self, file_path: str) -> bytes:
        return b""

    async def delete(self, file_path: str) -> None:
        return None

    async def exists(self, file_path: str) -> bool:
        return True
```

`app/core/config.py`의 OCR 설정 블록(`ocr_stuck_timeout_seconds` 아래)에 추가:

```python
    ocr_stuck_timeout_seconds: int = 300
    local_storage_dir: str = "var/ocr_tmp"
```

`.gitignore` 끝에 추가:

```
# OCR 로컬 임시 저장
var/
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/infrastructure/storage/test_local_file_storage.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: 전체 회귀 확인 + 커밋**

Run: `python -m pytest -q && ruff check app/ tests/`
Expected: 전부 PASS (StubFileStorage의 upload 명 유지로 기존 테스트 영향 없음)

```bash
git add app/infrastructure/storage/file_storage.py app/core/config.py .gitignore tests/infrastructure/storage/
git commit -m "feat(storage): LocalFileStorage 및 read/exists 인터페이스 추가"
```

---

### Task 3: Clova base64 입력 — OcrClient/Clova/Service 호출부 동시 전환

**Files:**
- Modify: `app/infrastructure/ocr/ocr_client.py`
- Modify: `app/infrastructure/ocr/clova_client.py`
- Modify: `app/domains/ocr/service.py:61-112` (`process_job`, `_recognize_with_retry`)
- Modify: `tests/infrastructure/ocr/test_clova_client.py`
- Modify: `tests/infrastructure/ocr/test_ocr_client.py`
- Modify: `tests/domains/ocr/test_service.py` (fake 클라이언트 시그니처)

**Interfaces:**
- Produces: `OcrClient.recognize(self, image: bytes, image_format: str) -> OcrResultDTO`.
- Produces: `OcrService._recognize_with_retry(self, image: bytes, image_format: str) -> OcrResultDTO`.
- Consumes: `app.infrastructure.ocr.format.detect_image_format`(Task 1), `FileStorage.read`(Task 2).

> 참고: 이 태스크는 `recognize` 시그니처를 바꾸므로 클라이언트·서비스·관련 테스트 fake를 **한 커밋에서 함께** 갱신해야 그린이 유지된다.

- [ ] **Step 1: 기존 테스트를 새 시그니처로 수정(실패 유도)**

`tests/infrastructure/ocr/test_clova_client.py`에서 `recognize` 호출과 payload 단언을 바이트/base64 기준으로 변경. 핵심 단언 추가:

```python
import base64

# recognize 호출을 바이트 입력으로
result = await client.recognize(b"\x89PNG\r\n\x1a\n", image_format="png")

# 캡처된 요청 payload 검증 (httpx MockTransport 사용 부분)
sent = captured_request_json["images"][0]
assert sent["format"] == "png"
assert "url" not in sent
assert base64.b64decode(sent["data"]) == b"\x89PNG\r\n\x1a\n"
```

`tests/infrastructure/ocr/test_ocr_client.py`의 Stub 호출도 `recognize(b"x", image_format="png")` 형태로 수정.

`tests/domains/ocr/test_service.py`의 모든 fake OCR 클라이언트(`FakeOcrClient`, `SequenceOcrClient`, `DeletingOcrClient`, `ConcurrentDeletingOcrClient`, worker 테스트의 `FakeClient`)의 메서드 시그니처를 `async def recognize(self, image, image_format="png")`로 변경(인자만 받고 기존 반환 유지).

- [ ] **Step 2: Run to verify failures**

Run: `python -m pytest tests/infrastructure/ocr/test_clova_client.py tests/infrastructure/ocr/test_ocr_client.py -v`
Expected: FAIL — `recognize() got unexpected keyword argument 'image_format'` 또는 payload 단언 실패

- [ ] **Step 3: 구현 변경**

`app/infrastructure/ocr/ocr_client.py`:

```python
from typing import Protocol

from app.infrastructure.ocr.ocr_dto import OcrResultDTO


class OcrClient(Protocol):
    """OCR 엔진 호출 인터페이스입니다. Clova → 타 엔진으로 교체 가능합니다."""

    async def recognize(self, image: bytes, image_format: str) -> OcrResultDTO: ...


class StubOcrClient:
    """개발/테스트용 stub 구현입니다."""

    async def recognize(self, image: bytes, image_format: str) -> OcrResultDTO:
        raise NotImplementedError
```

`app/infrastructure/ocr/clova_client.py`의 `recognize`를 교체:

```python
import base64
# ... 기존 import 유지 (time, uuid, httpx) ...

    async def recognize(self, image: bytes, image_format: str) -> OcrResultDTO:
        payload = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "images": [
                {
                    "format": image_format,
                    "name": "checkup",
                    "data": base64.b64encode(image).decode("ascii"),
                }
            ],
        }
        headers = {"X-OCR-SECRET": self._secret_key}
        if self._http_client is not None:
            response = await self._http_client.post(
                self._invoke_url, json=payload, headers=headers, timeout=self._timeout
            )
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                response = await http.post(self._invoke_url, json=payload, headers=headers)
        response.raise_for_status()
        return self._to_dto(response.json())
```

`app/domains/ocr/service.py`:
- import 추가: `from app.infrastructure.ocr.format import detect_image_format`
- `process_job`의 인식 구간을 바이트 입력으로 변경:

```python
        try:
            image = await self._file_storage.read(record.file_url)
            image_format = detect_image_format(image) or "png"
            result = await self._recognize_with_retry(image, image_format)
        except Exception as exc:  # noqa: BLE001
            self._mark_processing_failure(job, "recognize_failed", exc)
            return
```

- `_recognize_with_retry` 시그니처/본문 변경:

```python
    async def _recognize_with_retry(self, image: bytes, image_format: str) -> OcrResultDTO:
        last_error: Exception | None = None
        for _ in range(self._max_retries + 1):
            try:
                return await self._ocr_client.recognize(image, image_format)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
        if last_error is None:
            raise RuntimeError("OCR recognition was not attempted")
        raise last_error
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/infrastructure/ocr/ tests/domains/ocr/test_service.py -v`
Expected: PASS (StubFileStorage.read가 `b""`를 반환하나, 서비스 테스트는 FakeFileStorage/실 LocalStorage를 쓰며 fake 클라이언트가 바이트를 무시하고 고정 결과 반환하므로 통과)

> 주의: `tests/domains/ocr/test_service.py`의 일부 fake `FileStorage`는 `read`가 필요하다. fake에 `async def read(self, p): return b"\x89PNG\r\n\x1a\n"`를 추가한다(없으면 AttributeError).

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/ocr/ocr_client.py app/infrastructure/ocr/clova_client.py app/domains/ocr/service.py tests/
git commit -m "feat(ocr): Clova 입력을 URL에서 base64 data(바이트)로 전환"
```

---

### Task 4: claim_job + process_single + 성공 시 이미지 삭제 + raw 코드 제거

**Files:**
- Modify: `app/domains/ocr/repository.py` (`claim_job` 추가, `mark_completed`에서 `raw_result_url` 제거)
- Modify: `app/domains/ocr/service.py` (`process_single` 추가, 성공 시 `delete`, `_store_raw`/`_discard_raw` 제거)
- Modify: `app/domains/record/repository.py:142-160` (`delete_record_cascade`에서 `job.raw_result_url` 참조 제거)
- Modify: `tests/domains/ocr/test_service.py` (raw 관련 테스트 제거/대체, process_single·delete 테스트 추가)

**Interfaces:**
- Produces: `OcrRepository.claim_job(self, job_id: int) -> OcrJob | None` — `status=PENDING`인 해당 잡만 `PROCESSING`으로 전환 후 반환, 아니면 None.
- Produces: `OcrRepository.mark_completed(self, job: OcrJob, parsed_field_count: int) -> None` (raw 인자 제거).
- Produces: `OcrService.process_single(self, job_id: int) -> None`.

- [ ] **Step 1: Write failing tests**

`tests/domains/ocr/test_service.py`에 추가(그리고 raw 관련 기존 테스트 `test_raw_storage_failure_does_not_fail_processing`, `test_concurrent_delete_after_raw_upload_compensates_file`, oversized raw 단언 제거):

```python
@pytest.mark.asyncio
async def test_process_single_claims_and_deletes_image_on_success(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "checkups/1/h.png", "h")
    db_session.commit()
    storage = FakeFileStorage()  # read는 유효 PNG 바이트 반환하도록
    service = _make_service(db_session, FakeOcrClient(result=_glucose_result()), storage)
    job = await service.create_job(record.id, user_id=1)
    db_session.commit()

    await service.process_single(job.id)

    assert service.get_job(job.id).status == OcrStatus.COMPLETED.value
    assert "checkups/1/h.png" in storage.deletes  # 성공 시 이미지 삭제


@pytest.mark.asyncio
async def test_process_single_skips_when_not_pending(db_session):
    record_repo = RecordRepository(db_session)
    record = record_repo.create_record(1, "UPLOAD", "checkups/1/h.png", "h")
    db_session.commit()
    service = _make_service(db_session, FakeOcrClient(result=_glucose_result()))
    job = await service.create_job(record.id, user_id=1)
    job.status = OcrStatus.COMPLETED.value  # 이미 완료된 잡
    db_session.commit()

    await service.process_single(job.id)  # 예외 없이 skip

    assert service.get_job(job.id).status == OcrStatus.COMPLETED.value
```

`FakeFileStorage`(test_service.py 내)에 `read`/`deletes` 보강:

```python
class FakeFileStorage:
    def __init__(self, error=None):
        self.uploads = []
        self.deletes = []
        self._error = error

    async def upload(self, path, content):
        if self._error:
            raise self._error
        self.uploads.append((path, content))
        return path

    async def read(self, path):
        return b"\x89PNG\r\n\x1a\n"

    async def delete(self, path):
        self.deletes.append(path)

    async def exists(self, path):
        return True
```

- [ ] **Step 2: Run to verify failures**

Run: `python -m pytest tests/domains/ocr/test_service.py -v`
Expected: FAIL — `AttributeError: 'OcrService' object has no attribute 'process_single'`

- [ ] **Step 3: 구현**

`app/domains/ocr/repository.py`에 추가/수정:

```python
    def claim_job(self, job_id: int) -> OcrJob | None:
        stmt = (
            select(OcrJob)
            .where(OcrJob.id == job_id, OcrJob.status == OcrStatus.PENDING.value)
            .limit(1)
        )
        job = self._db.execute(stmt).scalar_one_or_none()
        if job is None:
            return None
        job.status = OcrStatus.PROCESSING.value
        job.requested_at = _now()
        self._db.flush()
        return job
```

`mark_completed`에서 raw 제거:

```python
    def mark_completed(self, job: OcrJob, parsed_field_count: int) -> None:
        job.status = OcrStatus.COMPLETED.value
        job.parsed_field_count = parsed_field_count
        job.completed_at = _now()
        self._db.flush()
```

`app/domains/ocr/service.py`:
- `_store_raw`/`_discard_raw` 메서드 삭제. `import json` 제거.
- `process_job`의 성공 블록을 raw 없이, 성공 후 이미지 삭제로 교체:

```python
        try:
            with self._ocr_repo.begin_nested():
                parsed = self._parser.parse(result)
                parsed_count = self._record_repo.upsert_ocr_metrics(job.record_id, parsed)
                self._ocr_repo.mark_completed(job, parsed_count)
                self._record_repo.set_ocr_status(record, OcrStatus.COMPLETED.value)
            self._ocr_repo.commit()
        except ValueError:
            self._mark_deleted_record_failure(job, "record_deleted_during_upsert")
            return
        except Exception as exc:  # noqa: BLE001
            self._ocr_repo.rollback()
            self._mark_processing_failure(job, "processing_failed", exc)
            return
        # 커밋 성공 이후에만 원본 이미지를 best-effort 삭제한다.
        try:
            await self._file_storage.delete(record.file_url)
        except Exception:  # noqa: BLE001
            pass
        logger.info("ocr_job_completed", extra={"job_id": job.id, "parsed_field_count": parsed_count})
```

- `process_single` 추가:

```python
    async def process_single(self, job_id: int) -> None:
        job = self._ocr_repo.claim_job(job_id)
        if job is None:
            self._ocr_repo.rollback()
            return
        self._ocr_repo.commit()
        try:
            await self.process_job(job)
        except Exception as exc:  # noqa: BLE001
            self._ocr_repo.rollback()
            logger.warning(
                "ocr_single_job_unhandled_failure",
                extra={"job_id": job_id, "error_type": type(exc).__name__},
            )
```

`app/domains/record/repository.py`의 `delete_record_cascade`에서 raw 수집 제거:

```python
        jobs = self._db.execute(
            select(OcrJob).where(OcrJob.record_id == record.id)
        ).scalars().all()
        for job in jobs:
            self._db.delete(job)
```

(상단의 `if job.raw_result_url: file_urls.append(...)` 라인 삭제. `file_urls`에는 이제 `record.file_url`만 들어간다.)

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/domains/ocr/ tests/domains/record/ -v`
Expected: PASS (raw 관련 제거 후 신규 테스트 포함 그린)

- [ ] **Step 5: Commit**

```bash
git add app/domains/ocr/repository.py app/domains/ocr/service.py app/domains/record/repository.py tests/
git commit -m "feat(ocr): process_single(claim) 및 성공 시 이미지 삭제, raw 저장 제거"
```

---

### Task 5: OcrJob.raw_result_url 컬럼 제거 + Alembic 마이그레이션

**Files:**
- Modify: `app/domains/ocr/models.py:20` (`raw_result_url` 컬럼 삭제)
- Create: `alembic/versions/<rev>_drop_raw_result_url.py`
- Test: `tests/domains/ocr/test_models.py` (raw 단언이 있으면 제거)

**Interfaces:**
- Consumes: Task 4에서 코드가 더 이상 `raw_result_url`을 참조하지 않음(전제).

- [ ] **Step 1: 모델에서 컬럼 제거 + 영향 테스트 조정**

`app/domains/ocr/models.py`에서 라인 삭제:

```python
    raw_result_url = Column(String(500), nullable=True)
```

`tests/domains/ocr/test_models.py`에 `raw_result_url` 참조가 있으면 삭제.

- [ ] **Step 2: 마이그레이션 생성**

Run: `alembic revision -m "drop ocr_jobs.raw_result_url"`
생성된 파일의 `upgrade`/`downgrade`를 작성:

```python
def upgrade() -> None:
    op.drop_column("ocr_jobs", "raw_result_url")


def downgrade() -> None:
    op.add_column(
        "ocr_jobs",
        sa.Column("raw_result_url", sa.String(length=500), nullable=True),
    )
```

(파일 상단에 `import sqlalchemy as sa`, `from alembic import op`, `down_revision = "97a644712a37"` 확인.)

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/domains/ocr/test_models.py tests/domains/ocr/test_repository.py -v`
Expected: PASS (모델에서 컬럼 제거, create_all 기반 테스트 정상)

- [ ] **Step 4: 마이그레이션 정합성 확인**

Run: `alembic upgrade head && alembic downgrade -1 && alembic upgrade head`
(로컬 DB 필요. CI/DB 미가용 시 SQL 리뷰로 대체하고 그 사실을 PR에 명시.)
Expected: 오류 없이 up/down 왕복.

- [ ] **Step 5: Commit**

```bash
git add app/domains/ocr/models.py alembic/versions/ tests/domains/ocr/test_models.py
git commit -m "feat(db): ocr_jobs.raw_result_url 컬럼 제거 마이그레이션"
```

---

### Task 6: 의존성 배선 — LocalFileStorage 통일 + 백그라운드 잡 러너

**Files:**
- Modify: `app/domains/ocr/dependencies.py`
- Modify: `app/database/session.py` (백그라운드용 세션 팩토리 노출)
- Test: `tests/domains/ocr/test_dependencies.py` (신규)
- Create: `tests/domains/ocr/test_dependencies.py`

**Interfaces:**
- Produces: `get_file_storage() -> FileStorage` → `LocalFileStorage(settings.local_storage_dir)`.
- Produces: `build_ocr_service(db: Session) -> OcrService` — 요청/백그라운드 공용 빌더.
- Produces: `get_ocr_job_runner() -> Callable[[int], Awaitable[None]]` — 독립 세션을 만들어 `process_single`을 실행하는 async 콜러블(테스트에서 override 가능).
- Consumes: `app.database.session.SessionLocal`(노출 필요).

- [ ] **Step 1: Write failing test**

```python
# tests/domains/ocr/test_dependencies.py
from app.domains.ocr.dependencies import build_ocr_service, get_file_storage
from app.infrastructure.storage.file_storage import LocalFileStorage


def test_get_file_storage_is_local():
    assert isinstance(get_file_storage(), LocalFileStorage)


def test_build_ocr_service_uses_injected_session(db_session):
    service = build_ocr_service(db_session)
    assert service is not None
    # 동일 세션으로 구성되어 잡 생성/조회가 동작
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/domains/ocr/test_dependencies.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_ocr_service'`

- [ ] **Step 3: 구현**

`app/database/session.py`에 백그라운드용 컨텍스트 헬퍼 추가(엔진 미설정 시 명확한 에러):

```python
from contextlib import contextmanager


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    if _SessionLocal is None:
        raise RuntimeError("DATABASE_URL이 설정되지 않았습니다.")
    db = _SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

`app/domains/ocr/dependencies.py` 교체:

```python
from collections.abc import Awaitable, Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database.session import get_db, session_scope
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.record.repository import RecordRepository
from app.domains.record.service import RecordService
from app.infrastructure.ocr.clova_client import ClovaOcrClient
from app.infrastructure.ocr.ocr_client import StubOcrClient
from app.infrastructure.ocr.parser import OcrParser
from app.infrastructure.storage.file_storage import FileStorage, LocalFileStorage


def get_file_storage() -> FileStorage:
    return LocalFileStorage(settings.local_storage_dir)


def _build_ocr_client():
    if settings.clova_ocr_invoke_url and settings.clova_ocr_secret_key:
        return ClovaOcrClient(
            invoke_url=settings.clova_ocr_invoke_url,
            secret_key=settings.clova_ocr_secret_key,
            timeout=settings.ocr_request_timeout_seconds,
        )
    return StubOcrClient()


def build_ocr_service(db: Session) -> OcrService:
    return OcrService(
        ocr_repo=OcrRepository(db),
        record_repo=RecordRepository(db),
        ocr_client=_build_ocr_client(),
        file_storage=get_file_storage(),
        parser=OcrParser(),
        max_retries=settings.ocr_max_retries,
    )


def get_ocr_service(db: Session = Depends(get_db)) -> OcrService:
    return build_ocr_service(db)


def get_record_service(db: Session = Depends(get_db)) -> RecordService:
    return RecordService(RecordRepository(db), get_file_storage())


def get_ocr_job_runner() -> Callable[[int], Awaitable[None]]:
    async def _run(job_id: int) -> None:
        with session_scope() as db:
            service = build_ocr_service(db)
            await service.process_single(job_id)

    return _run
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/domains/ocr/test_dependencies.py tests/domains/record/test_ocr_endpoints.py -v`
Expected: PASS (엔드포인트 테스트는 `get_file_storage`/`get_record_service` override로 기존대로 동작)

- [ ] **Step 5: Commit**

```bash
git add app/domains/ocr/dependencies.py app/database/session.py tests/domains/ocr/test_dependencies.py
git commit -m "feat(ocr): LocalFileStorage 배선 통일 및 백그라운드 잡 러너 의존성 추가"
```

---

### Task 7: 업로드 엔드포인트 — 포맷 검증 + 백그라운드 트리거

**Files:**
- Modify: `app/api/v1/record_router.py` (`upload_checkup`)
- Modify: `app/core/exceptions.py` (415 예외 추가)
- Modify: `tests/domains/record/test_ocr_endpoints.py`

**Interfaces:**
- Consumes: `detect_image_format`(Task 1), `get_ocr_job_runner`(Task 6), `get_file_storage`(Task 6).
- Produces: 업로드 시 미지원 포맷 → 415, 지원 포맷 → 임시 저장 + `BackgroundTasks`로 `runner(job_id)` 등록 + 202.

- [ ] **Step 1: Write failing tests**

`tests/domains/record/test_ocr_endpoints.py`의 `api` fixture에서 `get_ocr_job_runner`를 테스트 세션 기반으로 override하고, 업로드 후 OCR이 동기적으로 수행되는지(TestClient는 BackgroundTasks를 요청 내에서 실행) 검증:

```python
from app.domains.ocr.dependencies import build_ocr_service, get_ocr_job_runner

# fixture 내부:
async def _runner(job_id: int):
    await build_ocr_service(db_session).process_single(job_id)

app.dependency_overrides[get_ocr_job_runner] = lambda: _runner
```

테스트:

```python
def test_upload_rejects_unsupported_format(api):
    client, db = api
    resp = client.post(
        "/api/v1/records/checkups/upload",
        files={"file": ("a.gif", io.BytesIO(b"GIF89a..."), "image/gif")},
    )
    assert resp.status_code == 415


def test_upload_png_triggers_background_ocr(api):
    client, db = api
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    resp = client.post(
        "/api/v1/records/checkups/upload",
        files={"file": ("a.png", io.BytesIO(png), "image/png")},
    )
    assert resp.status_code == 202
    record_id = resp.json()["data"]["record_id"]
    # 백그라운드 러너(override)가 동기 실행되어 잡 상태가 진전됨
    from app.domains.ocr.repository import OcrRepository
    job = OcrRepository(db).get_job(resp.json()["data"]["ocr_job_id"])
    assert job.status in ("COMPLETED", "FAILED", "PROCESSING")
```

> 참고: 기존 `MemoryStorage`/StubOcrClient 조합에서 `recognize`가 `NotImplementedError`면 잡은 FAILED로 진전된다 — 트리거가 동작했음을 보이는 것으로 충분.

- [ ] **Step 2: Run to verify failures**

Run: `python -m pytest tests/domains/record/test_ocr_endpoints.py::test_upload_rejects_unsupported_format -v`
Expected: FAIL — 415가 아니라 202/500

- [ ] **Step 3: 구현**

`app/core/exceptions.py`에 추가:

```python
class UnsupportedMediaTypeException(AppException):
    def __init__(self, message: str = "지원하지 않는 파일 형식입니다.", error_code: str = "UNSUPPORTED_MEDIA_TYPE") -> None:
        super().__init__(status_code=415, message=message, error_code=error_code)
```

`app/api/v1/record_router.py`의 `upload_checkup` 교체(시그니처에 `BackgroundTasks`, `runner` 주입):

```python
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, BackgroundTasks, Depends, File, Response, UploadFile

from app.core.exceptions import UnsupportedMediaTypeException
from app.domains.ocr.dependencies import (
    get_file_storage,
    get_ocr_job_runner,
    get_ocr_service,
    get_record_service,
)
from app.infrastructure.ocr.format import detect_image_format


@router.post("/checkups/upload", status_code=202)
async def upload_checkup(
    response: Response,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    ocr_service: OcrService = Depends(get_ocr_service),
    file_storage: FileStorage = Depends(get_file_storage),
    runner: Callable[[int], Awaitable[None]] = Depends(get_ocr_job_runner),
):
    content = await file.read()
    image_format = detect_image_format(content)
    if image_format is None:
        raise UnsupportedMediaTypeException()
    file_hash = hashlib.sha256(content).hexdigest()
    record_repo = RecordRepository(db)
    existing = record_repo.find_by_user_and_hash(user_id, file_hash)
    if existing is not None:
        response.status_code = 200
        return success_response(
            message="이미 업로드된 검진 결과지입니다.",
            data=UploadResponse(record_id=existing.id, ocr_job_id=0).model_dump(),
        )
    key = f"checkups/{user_id}/{file_hash}.{image_format}"
    file_url = await file_storage.upload(key, content)
    try:
        record = record_repo.create_record(user_id, "UPLOAD", file_url, file_hash)
        db.flush()
        job = await ocr_service.create_job(record.id, user_id)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = record_repo.find_by_user_and_hash(user_id, file_hash)
        if existing is None:
            await _safe_delete(file_storage, file_url)
            raise
        response.status_code = 200
        return success_response(
            message="이미 업로드된 검진 결과지입니다.",
            data=UploadResponse(record_id=existing.id, ocr_job_id=0).model_dump(),
        )
    except Exception:
        db.rollback()
        await _safe_delete(file_storage, file_url)
        raise
    background_tasks.add_task(runner, job.id)
    return success_response(
        message="업로드 완료. OCR 처리를 시작합니다.",
        data=UploadResponse(record_id=record.id, ocr_job_id=job.id).model_dump(),
    )
```

(`FileStorage` import는 Task 이전부터 존재. `from app.infrastructure.storage.file_storage import FileStorage` 유지.)

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/domains/record/test_ocr_endpoints.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/v1/record_router.py app/core/exceptions.py tests/domains/record/test_ocr_endpoints.py
git commit -m "feat(record): 업로드 포맷 검증(415) 및 백그라운드 OCR 트리거"
```

---

### Task 8: reprocess — 이미지 존재 가드 + 백그라운드 트리거

**Files:**
- Modify: `app/api/v1/ocr_router.py` (`reprocess`)
- Test: `tests/domains/ocr/test_ocr_router.py`

**Interfaces:**
- Consumes: `FileStorage.exists`(Task 2), `get_ocr_job_runner`/`get_file_storage`(Task 6).
- Produces: 원본 이미지 없으면 409 `IMAGE_UNAVAILABLE`, 있으면 PENDING 재설정 + 백그라운드 트리거.

- [ ] **Step 1: Write failing tests**

```python
def test_reprocess_rejects_when_image_missing(api):
    client, db = api
    # 이미지가 없는 record (storage.exists=False 인 stub로 override)
    ...
    resp = client.post(f"/api/v1/records/ocr/checkups/{record_id}/reprocess")
    assert resp.status_code == 409
    assert resp.json()["error_code"] == "IMAGE_UNAVAILABLE"
```

(엔드포인트 prefix는 `app/api/v1/router.py`의 등록을 따른다. 정확한 경로는 라우터 include 확인 후 사용.)

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/domains/ocr/test_ocr_router.py -v`
Expected: FAIL — 409가 아님

- [ ] **Step 3: 구현**

`app/api/v1/ocr_router.py`의 `reprocess`:

```python
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, BackgroundTasks, Depends

from app.core.exceptions import ConflictException
from app.domains.ocr.dependencies import get_file_storage, get_ocr_job_runner, get_ocr_service
from app.infrastructure.storage.file_storage import FileStorage


@router.post("/checkups/{record_id}/reprocess")
async def reprocess(
    record_id: int,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user),
    db: Session = Depends(get_db),
    service: OcrService = Depends(get_ocr_service),
    file_storage: FileStorage = Depends(get_file_storage),
    runner: Callable[[int], Awaitable[None]] = Depends(get_ocr_job_runner),
):
    record_repo = RecordRepository(db)
    record = record_repo.get_record(record_id)
    if record is None:
        raise NotFoundException(message="검진 기록을 찾을 수 없습니다.")
    if record.user_id != user_id:
        raise ForbiddenException(message="해당 기록에 대한 권한이 없습니다.")
    if not record.file_url or not await file_storage.exists(record.file_url):
        raise ConflictException(
            message="원본 이미지가 없어 재처리할 수 없습니다.",
            error_code="IMAGE_UNAVAILABLE",
        )
    record_repo.reset_verification(record)
    record_repo.set_ocr_status(record, "PENDING")
    job = await service.create_job(record_id, user_id)
    db.commit()
    background_tasks.add_task(runner, job.id)
    return success_response(
        message="OCR 재처리를 요청했습니다.",
        data={"record_id": record_id, "ocr_job_id": job.id},
    )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/domains/ocr/test_ocr_router.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app/api/v1/ocr_router.py tests/domains/ocr/test_ocr_router.py
git commit -m "feat(ocr): reprocess 이미지 존재 가드 및 백그라운드 트리거"
```

---

### Task 9: 스케줄러(APScheduler) + lifespan 배선 (복구 배치)

**Files:**
- Modify: `requirements.txt` (`apscheduler` 추가)
- Modify: `app/workers/scheduler.py`
- Modify: `app/main.py` (lifespan에서 start/stop)
- Test: `tests/workers/test_scheduler.py` (신규)

**Interfaces:**
- Consumes: `run_ocr_batch`(기존), `build_ocr_service`/`session_scope`(Task 6), `settings.ocr_polling_interval_seconds`, `settings.ocr_stuck_timeout_seconds`.
- Produces: `start_scheduler() -> None`(AsyncIOScheduler 기동, `run_ocr_batch` 주기 등록), `stop_scheduler() -> None`, 그리고 한 틱 실행용 `async def _ocr_batch_tick() -> int`.

- [ ] **Step 1: Write failing test**

```python
# tests/workers/test_scheduler.py
import pytest

from app.workers import scheduler


@pytest.mark.asyncio
async def test_ocr_batch_tick_runs_recovery(db_session, monkeypatch):
    # session_scope가 테스트 세션을 쓰도록 패치
    import contextlib

    @contextlib.contextmanager
    def _scope():
        yield db_session

    monkeypatch.setattr(scheduler, "session_scope", _scope)
    processed = await scheduler._ocr_batch_tick()
    assert processed == 0  # PENDING 없음 → 0


def test_start_scheduler_registers_job():
    scheduler.start_scheduler()
    try:
        assert scheduler._scheduler is not None
        assert len(scheduler._scheduler.get_jobs()) >= 1
    finally:
        scheduler.stop_scheduler()
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/workers/test_scheduler.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute '_ocr_batch_tick'` / `NotImplementedError`

- [ ] **Step 3: 의존성 추가 + 구현**

`requirements.txt`에 추가: `apscheduler==3.10.4`
Run: `pip install apscheduler==3.10.4`

`app/workers/scheduler.py` 교체:

```python
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import settings
from app.database.session import session_scope
from app.domains.ocr.dependencies import build_ocr_service
from app.domains.ocr.repository import OcrRepository
from app.workers.ocr_worker import run_ocr_batch

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _ocr_batch_tick() -> int:
    with session_scope() as db:
        service = build_ocr_service(db)
        return await run_ocr_batch(
            service, OcrRepository(db), settings.ocr_stuck_timeout_seconds
        )


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _ocr_batch_tick,
        "interval",
        seconds=settings.ocr_polling_interval_seconds,
        max_instances=1,
        id="ocr_batch",
    )
    _scheduler.start()
    logger.info("scheduler_started")


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
```

`app/main.py`의 lifespan 교체:

```python
from app.workers.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_scheduler()
    yield
    stop_scheduler()
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/workers/test_scheduler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add requirements.txt app/workers/scheduler.py app/main.py tests/workers/test_scheduler.py
git commit -m "feat(worker): APScheduler로 OCR 복구 배치 주기 실행 및 lifespan 배선"
```

---

### Task 10: 전체 회귀 + 문서 갱신

**Files:**
- Modify: `docs/implementation-status.md`

- [ ] **Step 1: 전체 테스트 + 린트**

Run: `python -m pytest -q && ruff check app/ tests/`
Expected: 전부 PASS

- [ ] **Step 2: 구현 현황 문서 갱신**

`docs/implementation-status.md`에 OCR 요청-즉시-실행/로컬 임시 저장/복구 배치 완료 항목 반영.

- [ ] **Step 3: Commit**

```bash
git add docs/implementation-status.md
git commit -m "docs: OCR 요청 즉시 실행/로컬 임시 저장/복구 배치 구현 현황 반영"
```

---

## Self-Review

**Spec coverage:**
- 트리거 모델(BackgroundTasks+202) → Task 6(러너), Task 7(트리거). ✅
- 로컬 임시 저장 + 성공 시 삭제 → Task 2(LocalFileStorage), Task 4(delete-on-success). ✅
- Clova base64 + jpg/jpeg/png → Task 1(포맷), Task 3(base64). ✅
- 배치 복구(스케줄러) → Task 9. ✅
- reprocess 이미지 가드 → Task 8. ✅
- stuck→FAILED 유지 → 기존 `recover_stuck` 그대로(변경 없음). ✅
- raw JSON 폐지 → Task 4(코드), Task 5(컬럼/마이그레이션). ✅
- config `local_storage_dir` → Task 2. ✅

**Placeholder scan:** 각 코드 스텝에 실제 코드/명령/기대출력 포함. 단, Task 8의 reprocess 경로 prefix는 `app/api/v1/router.py` 등록을 따르며 실행 시 확인(테스트가 강제).

**Type consistency:** `recognize(image: bytes, image_format: str)`(Task 3) ↔ `_recognize_with_retry`(Task 3) ↔ fake 클라이언트(Task 3) 일치. `claim_job`/`process_single`(Task 4) ↔ 러너(Task 6) ↔ 트리거(Task 7) 일치. `mark_completed(job, parsed_field_count)`(Task 4)에서 raw 인자 제거 후 호출부 일치.

## 알려진 편차
- 스펙의 `FileStorage.upload`→`save` 리네임은 생략(기존 `upload` 유지). 동작 동일, 리포 전반 churn 최소화 목적. `read`/`exists`만 신규 추가.
