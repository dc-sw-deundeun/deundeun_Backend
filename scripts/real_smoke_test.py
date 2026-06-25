"""실DB(deundeun) 대상 OCR 동기 업로드 파이프라인 엔드투엔드 스모크 테스트.

실행: DATABASE_URL 설정 후 `python scripts/real_smoke_test.py`
- 앱 부팅(/health, 라우트 수) 확인
- 실제 Postgres에 두 단계 OCR 업로드(preview → commit) → metric 영속화 → 검수 → 분석 게이트
"""

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.domains.analysis.service import AnalysisService
from app.domains.ocr.models import OcrJob
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import FinalMetric, OcrService
from app.domains.record.repository import RecordRepository
from app.infrastructure.ocr.ocr_dto import OcrFieldDTO, OcrResultDTO
from app.infrastructure.ocr.parser import OcrParser


class FakeClovaClient:
    """실제 검진표를 닮은 합성 Clova 결과를 반환(네트워크 없이 파이프라인 검증)."""

    async def recognize(self, image: bytes, image_format: str) -> OcrResultDTO:
        def f(text, x, y, conf=0.95):
            return OcrFieldDTO(text=text, confidence=conf, x_min=x, x_max=x + 30, y_center=y)

        return OcrResultDTO(
            fields=[
                f("공복혈당", 10, 100),
                f("109", 130, 100),
                f("100 미만", 320, 100),
                f("체질량지수", 10, 150),
                f("24.1", 130, 150),
                f("혈색소", 10, 200),
                f("16.6", 130, 200),
                f("혈압", 10, 250),
                f("110", 130, 250),
                f("/", 165, 250),
                f("70", 190, 250),
                f("AST", 10, 300),
                f("21", 130, 300),
                f("ALT", 10, 350),
                f("23", 130, 350),
                f("요단백", 10, 400),
                f("음성(-)", 130, 400),
            ]
        )


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
        ocr_repo=ocr_repo,
        record_repo=record_repo,
        ocr_client=FakeClovaClient(),
        parser=OcrParser(),
    )
    try:
        # Step 1: OCR 미리보기 (DB 기록 없음)
        preview = await service.process_upload(
            user_id=9001,
            images=[b"\x89PNG\r\n\x1a\n" + b"\x00" * 32],
        )
        print(
            f"[PREVIEW] page_count={preview.page_count} failed={preview.failed_pages} "
            f"status={preview.ocr_status} metric_count={len(preview.metrics)}"
        )
        assert (
            db.execute(
                __import__("sqlalchemy").text(
                    "SELECT COUNT(*) FROM checkup_records WHERE user_id=9001"
                )
            ).scalar()
            == 0
        ), "preview 단계에서 DB 기록이 생성되면 안 됩니다"
        print("[PREVIEW] DB 기록 없음 확인 OK")

        # 사용자 수동 수정 시뮬레이션 (BMI 값 변경)
        final_metrics = []
        for m in preview.metrics:
            if m.metric_code == "bmi":
                final_metrics.append(
                    FinalMetric(
                        metric_code=m.metric_code,
                        metric_name=m.metric_name,
                        value="24.2",
                        unit=m.unit,
                        confidence=m.confidence,
                        raw_text=m.raw_text,
                        page_index=m.page_index,
                        is_edited=True,
                    )
                )
            else:
                final_metrics.append(
                    FinalMetric(
                        metric_code=m.metric_code,
                        metric_name=m.metric_name,
                        value=m.value,
                        unit=m.unit,
                        confidence=m.confidence,
                        raw_text=m.raw_text,
                        page_index=m.page_index,
                    )
                )

        # Step 2: 커밋 (DB 영속화 + 자동 검수)
        commit = service.commit_upload(
            user_id=9001,
            ocr_status=preview.ocr_status,
            failed_pages=preview.failed_pages,
            metrics=final_metrics,
        )
        record = record_repo.get_record(commit.record_id)
        assert record is not None
        job = db.query(OcrJob).filter(OcrJob.record_id == commit.record_id).one()
        print(
            f"[COMMIT] record_id={commit.record_id} ocr_status={record.ocr_status} "
            f"verification_status={record.verification_status}"
        )
        print(f"[COMMIT] audit_job -> status={job.status} parsed={job.parsed_field_count}")

        metrics = {m.metric_code: m for m in record_repo.list_metrics(commit.record_id)}
        print("[COMMIT] 영속화된 metric (실DB 조회):")
        for code, m in sorted(metrics.items()):
            print(
                f"        {code:18} = {m.value:8} {m.unit or '':6} "
                f"src={m.source} conf={m.confidence} edited={m.is_edited}"
            )
        bmi = metrics.get("bmi")
        assert bmi is not None and bmi.value == "24.2" and bmi.is_edited is True
        print("[COMMIT] BMI 수동 수정값 확인 OK")

        # 분석 게이트: 커밋 직후 이미 VERIFIED이므로 바로 통과
        assert record.verification_status == "VERIFIED"
        analysis = AnalysisService(record_repo=record_repo)
        analysis.ensure_verified(commit.record_id)
        print("[GATE] 커밋 후 ensure_verified -> 통과 OK (자동 검수)")

        # 정리
        record_repo.delete_record_cascade(record)
        db.commit()
        print("[CLEAN] record/job/metric 삭제 완료")
        remaining = record_repo.list_metrics(commit.record_id)
        print(f"[CLEAN] 잔여 metric: {len(remaining)} (0 기대)")
        print("[RESULT] 실DB 엔드투엔드 파이프라인 PASS")
    finally:
        db.close()
        engine.dispose()


if __name__ == "__main__":
    boot_smoke()
    asyncio.run(pipeline_smoke())
