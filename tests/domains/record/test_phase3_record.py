from sqlalchemy.orm import Session

from app.domains.health_metric.repository import HealthMetricRepository
from app.domains.ocr.repository import OcrRepository
from app.domains.ocr.service import FinalMetric, OcrService
from app.domains.ocr.status import OcrStatus
from app.domains.onboarding.repository import OnboardingRepository
from app.domains.record.repository import RecordRepository
from app.domains.record.schemas import CommitMetricRequest, ManualCheckupRequest
from app.domains.record.service import RecordService
from app.domains.user.models import OnboardingStep, User
from app.infrastructure.ocr.ocr_client import StubOcrClient
from app.infrastructure.ocr.parser import OcrParser


def _service(db_session: Session) -> RecordService:
    return RecordService(
        RecordRepository(db_session),
        OnboardingRepository(db_session),
        HealthMetricRepository(db_session),
    )


def _create_user(db_session: Session, user_id: int = 1) -> None:
    user = User(
        id=user_id,
        email=f"user{user_id}@example.com",
        password_hash="hash",
        nickname="tester",
        onboarding_step=OnboardingStep.INITIAL_CHECKUP.value,
    )
    db_session.add(user)
    db_session.commit()


def test_list_checkups_pagination(db_session: Session) -> None:
    _create_user(db_session)
    service = _service(db_session)
    repo = RecordRepository(db_session)
    for _ in range(3):
        repo.create_record(1, "MANUAL", ocr_status=OcrStatus.COMPLETED.value)
    db_session.commit()

    page1 = service.list_checkups(1, page=1, size=2)
    assert page1.total == 3
    assert len(page1.items) == 2

    page2 = service.list_checkups(1, page=2, size=2)
    assert len(page2.items) == 1


def test_manual_create_and_get_detail(db_session: Session) -> None:
    _create_user(db_session)
    service = _service(db_session)
    record = service.create_manual(
        1,
        ManualCheckupRequest(
            metrics=[
                CommitMetricRequest(
                    metric_code="fasting_glucose",
                    metric_name="공복혈당",
                    value="95",
                    unit="mg/dL",
                )
            ]
        ),
    )
    detail = service.get_checkup(1, record.id)
    assert detail.source_type == "MANUAL"
    assert detail.verification_status == "UNVERIFIED"
    assert detail.metrics[0].status == "NORMAL"


def test_trends_returns_series(db_session: Session) -> None:
    _create_user(db_session)
    service = _service(db_session)
    first = service.create_manual(
        1,
        ManualCheckupRequest(
            metrics=[
                CommitMetricRequest(
                    metric_code="fasting_glucose",
                    metric_name="공복혈당",
                    value="90",
                    unit="mg/dL",
                )
            ]
        ),
    )
    second = service.create_manual(
        1,
        ManualCheckupRequest(
            metrics=[
                CommitMetricRequest(
                    metric_code="fasting_glucose",
                    metric_name="공복혈당",
                    value="100",
                    unit="mg/dL",
                )
            ]
        ),
    )
    trends = service.get_trends(1, second.id)
    assert trends.trends[0].metric_code == "fasting_glucose"
    assert len(trends.trends[0].points) == 2
    assert trends.trends[0].points[0].record_id == first.id


def test_verify_persists_metric_evaluation_to_db(db_session: Session) -> None:
    _create_user(db_session)
    service = _service(db_session)
    record = service.create_manual(
        1,
        ManualCheckupRequest(
            metrics=[
                CommitMetricRequest(
                    metric_code="bmi",
                    metric_name="체질량지수",
                    value="22.0",
                    unit="kg/m2",
                )
            ]
        ),
    )
    service.verify(1, record.id, None)
    db_session.commit()

    metric = RecordRepository(db_session).list_metrics(record.id)[0]
    assert metric.status == "NORMAL"
    assert metric.reference_min is not None
    assert metric.reference_max is not None


def test_verify_advances_onboarding_step(db_session: Session) -> None:
    _create_user(db_session)
    service = _service(db_session)
    record = service.create_manual(
        1,
        ManualCheckupRequest(
            metrics=[
                CommitMetricRequest(
                    metric_code="bmi",
                    metric_name="체질량지수",
                    value="22.0",
                    unit="kg/m2",
                )
            ]
        ),
    )
    service.verify(1, record.id, None)
    db_session.commit()
    user = OnboardingRepository(db_session).get_user_by_id(1)
    assert user is not None
    assert user.onboarding_step == OnboardingStep.CHECKUP_VERIFIED.value


def test_duplicate_content_hash_returns_existing(db_session: Session) -> None:
    _create_user(db_session)
    ocr_service = OcrService(
        ocr_repo=OcrRepository(db_session),
        record_repo=RecordRepository(db_session),
        ocr_client=StubOcrClient(),
        parser=OcrParser(),
    )
    content_hash = "b" * 64
    first = ocr_service.commit_upload(
        1,
        ocr_status=OcrStatus.COMPLETED.value,
        failed_pages=[],
        content_hash=content_hash,
        metrics=[
            FinalMetric(
                metric_code="fasting_glucose",
                metric_name="공복혈당",
                value="100",
                unit="mg/dL",
                confidence=0.9,
                raw_text="100",
                page_index=0,
            )
        ],
    )
    second = ocr_service.commit_upload(
        1,
        ocr_status=OcrStatus.COMPLETED.value,
        failed_pages=[],
        content_hash=content_hash,
        metrics=[
            FinalMetric(
                metric_code="fasting_glucose",
                metric_name="공복혈당",
                value="100",
                unit="mg/dL",
                confidence=0.9,
                raw_text="100",
                page_index=0,
            )
        ],
    )
    assert second.is_duplicate is True
    assert second.record_id == first.record_id
