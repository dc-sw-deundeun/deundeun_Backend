"""실DB(deundeun) 대상 OCR 파이프라인 엔드투엔드 스모크 테스트.

실행: DATABASE_URL 설정 후 `python scripts/real_smoke_test.py`
- 앱 부팅(/health, 라우트 수) 확인
- 실제 Postgres에 record/job 생성 → OCR(합성 결과) → 파서 → metric 영속화 → 검수 → 분석 게이트
"""

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.exceptions import ConflictException
from app.domains.analysis.service import AnalysisService
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import OcrService
from app.domains.record.repository import RecordRepository
from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser
from app.infrastructure.storage.file_storage import StubFileStorage


class FakeClovaClient:
    """실제 검진표를 닮은 합성 Clova 결과를 반환(네트워크 없이 파이프라인 검증)."""

    async def recognize(self, image: bytes, image_format: str) -> OcrResultDTO:
        def f(text, x, y, conf=0.95):
            return OcrFieldDTO(text=text, confidence=conf, x_min=x, x_max=x + 30, y_center=y)

        return OcrResultDTO(fields=[
            f("공복혈당", 10, 100), f("109", 130, 100), f("100 미만", 320, 100),
            f("체질량지수", 10, 150), f("24.1", 130, 150),
            f("혈색소", 10, 200), f("16.6", 130, 200),
            f("혈압", 10, 250), f("110", 130, 250), f("/", 165, 250), f("70", 190, 250),
            f("AST", 10, 300), f("21", 130, 300),
            f("ALT", 10, 350), f("23", 130, 350),
            f("요단백", 10, 400), f("음성(-)", 130, 400),
        ])


def boot_smoke():
    from app.main import app

    client = TestClient(app)
    health = client.get("/health")
    openapi = client.get("/openapi.json").json()
    ocr_routes = sorted(p for p in openapi["paths"] if "/ocr/" in p or "/records/" in p)
    print(f"[BOOT] /health -> {health.status_code} {health.json()}")
    print(f"[BOOT] OCR/record routes registered: {len(ocr_routes)}")
    for r in ocr_routes:
        print(f"        {r}")


async def pipeline_smoke():
    assert settings.database_url, "DATABASE_URL 미설정"
    print(f"[DB]   {settings.database_url}")
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = Session()
    record_repo = RecordRepository(db)
    ocr_repo = OcrRepository(db)
    service = OcrService(
        ocr_repo=ocr_repo, record_repo=record_repo,
        ocr_client=FakeClovaClient(), file_storage=StubFileStorage(),
        parser=OcrParser(),
    )
    try:
        record = record_repo.create_record(
            user_id=9001, source_type="UPLOAD",
            file_url="s3://stub/checkups/9001/sample.png", file_hash="smoke-hash-001",
        )
        db.flush()
        job = await service.create_job(record.id, user_id=9001)
        db.commit()
        print(f"[STEP] record_id={record.id} ocr_job_id={job.id} (ocr_status={record.ocr_status})")

        await service.process_job(job)
        db.commit()
        db.refresh(record)
        print(f"[STEP] process_job -> job.status={job.status} parsed={job.parsed_field_count} record.ocr_status={record.ocr_status}")

        metrics = {m.metric_code: m for m in record_repo.list_metrics(record.id)}
        print("[STEP] 영속화된 metric (실DB 조회):")
        for code, m in sorted(metrics.items()):
            print(f"        {code:18} = {m.value:8} {m.unit or '':6} src={m.source} conf={m.confidence}")

        # 분석 게이트: 검수 전이면 409
        analysis = AnalysisService(record_repo=record_repo)
        try:
            analysis.ensure_verified(record.id)
            print("[GATE] 검수 전 ensure_verified -> 예외 없음 (FAIL 기대했음)")
        except ConflictException as exc:
            print(f"[GATE] 검수 전 ensure_verified -> 409 차단 OK ({exc.error_code})")

        # 사용자 수동 수정 + 검수
        bmi = metrics["bmi"]
        record_repo.update_metric_value(bmi, "24.2", "kg/m2")
        record_repo.set_verified(record)
        db.commit()
        analysis.ensure_verified(record.id)  # 이제 통과해야 함
        db.refresh(bmi)
        print(f"[GATE] 검수 후 ensure_verified -> 통과 OK / bmi 수정값={bmi.value} src={bmi.source} edited={bmi.is_edited}")

        # 정리
        urls = record_repo.delete_record_cascade(record)
        db.commit()
        print(f"[CLEAN] record/job/metric 삭제 완료, 정리 대상 파일 {len(urls)}개")
        remaining = record_repo.list_metrics(record.id)
        print(f"[CLEAN] 잔여 metric: {len(remaining)} (0 기대)")
        print("[RESULT] 실DB 엔드투엔드 파이프라인 PASS")
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    boot_smoke()
    asyncio.run(pipeline_smoke())
