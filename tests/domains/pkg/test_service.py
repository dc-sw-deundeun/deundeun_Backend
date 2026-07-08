"""PkgService.build_pkg + GET /pkg 엔드포인트.

DB가 필요해 db_session/client 픽스처(Postgres testcontainers)를 사용한다 — 미가용 시 skip.
스냅샷 영속(pkg_snapshots) 자체는 test_persistence.py가 검증한다.
"""

import pytest

from app.core.exceptions import NotFoundException
from app.domains.analysis.repository import AnalysisRepository
from app.domains.health_metric.models import HealthMetricAnalysis
from app.domains.health_metric.repository import HealthMetricAnalysisRepository
from app.domains.pkg.repository import PkgRepository
from app.domains.pkg.service import PkgService
from app.domains.record.models import CheckupMetricResult, CheckupRecord
from app.domains.record.repository import RecordRepository
from app.domains.user.models import OnboardingStep, User


def _create_user(db, user_id):
    db.add(
        User(
            id=user_id,
            email=f"pkg-{user_id}@example.com",
            password_hash="hash",
            nickname=f"pkg-user-{user_id}",
            onboarding_step=OnboardingStep.INITIAL_CHECKUP.value,
            timezone="Asia/Seoul",
        )
    )
    db.commit()


def _service(db):
    return PkgService(
        RecordRepository(db),
        AnalysisRepository(db),
        HealthMetricAnalysisRepository(db),
        PkgRepository(db),
    )


def _seed_hm_analysis(db, user_id, record_id, items):
    """health_metric 평가 결과물(results_payload) 시드 — PKG 1순위 소스."""
    db.add(
        HealthMetricAnalysis(
            user_id=user_id,
            record_id=record_id,
            request_payload={},
            results_payload=items,
            explanation_payload={},
            summary_payload={},
            details_payload=[],
        )
    )
    db.commit()


def _seed_record(db, user_id, metrics, *, verified=True):
    record = CheckupRecord(
        user_id=user_id,
        source_type="MANUAL",
        verification_status="VERIFIED" if verified else "UNVERIFIED",
    )
    db.add(record)
    db.flush()
    for code, value in metrics:
        db.add(
            CheckupMetricResult(
                record_id=record.id,
                metric_code=code,
                metric_name=code,
                value=value,
                source="MANUAL",
            )
        )
    db.commit()
    return record


def test_build_pkg_derives_conditions_flags_and_fallback_edges(db_session) -> None:
    _create_user(db_session, 1)  # pkg_snapshots.user_id는 users FK
    _seed_record(db_session, 1, [("systolic_bp", "150"), ("fasting_glucose", "130")])
    pkg = _service(db_session).build_pkg(1)

    assert pkg.id == "user-1"
    assert set(pkg.conditions) == {"hypertension", "type2_diabetes"}
    assert pkg.flags.get("cardiovascular_risk") is True
    assert pkg.medications == []
    # 큐레이션 시드 엣지(고혈압→심혈관질환)
    assert any(e.src == "hypertension" and e.dst == "cardiovascular_disease" for e in pkg.edges)
    # 엣지 endpoint는 모두 노드로 존재
    node_ids = {n.id for n in pkg.nodes}
    assert all(e.src in node_ids and e.dst in node_ids for e in pkg.edges)


def test_build_pkg_404_without_verified_record(db_session) -> None:
    _seed_record(db_session, 2, [("systolic_bp", "150")], verified=False)
    with pytest.raises(NotFoundException):
        _service(db_session).build_pkg(2)


def test_build_pkg_uses_latest_verified_record(db_session) -> None:
    _create_user(db_session, 3)
    _seed_record(db_session, 3, [("fasting_glucose", "110")])  # prediabetes (older)
    _seed_record(db_session, 3, [("fasting_glucose", "130")])  # type2_diabetes (newer)
    pkg = _service(db_session).build_pkg(3)
    assert pkg.conditions == ["type2_diabetes"]


def test_build_pkg_populates_metric_trends(db_session) -> None:
    # 같은 지표를 시점별로 두 번 검진 → 추세(상승)가 PKG에 채워진다.
    _create_user(db_session, 11)
    _seed_record(db_session, 11, [("systolic_bp", "130")])  # 이전
    _seed_record(db_session, 11, [("systolic_bp", "150")])  # 최근 → 상승
    pkg = _service(db_session).build_pkg(11)

    bp = next((t for t in pkg.trends if t.code == "BP_SYS"), None)
    assert bp is not None
    assert bp.direction == "up"
    assert bp.adverse is True  # 혈압 상승 = 불리
    assert bp.points == 2


def test_build_pkg_single_record_has_no_trends(db_session) -> None:
    # 관측이 1회뿐이면 추세를 만들지 않는다(방향 판단 불가).
    _create_user(db_session, 12)
    _seed_record(db_session, 12, [("systolic_bp", "150")])
    pkg = _service(db_session).build_pkg(12)
    assert pkg.trends == []


def test_build_pkg_prefers_healthmetric_evaluated_result(db_session) -> None:
    # record 원시 수치는 정상(systolic 120)이지만, health_metric 결과물엔 위험 판정이 있다.
    _create_user(db_session, 5)  # HealthMetricAnalysis.user_id는 users FK
    record = _seed_record(db_session, 5, [("systolic_bp", "120")])
    _seed_hm_analysis(
        db_session,
        5,
        record.id,
        [
            {"canonical_test_code": "FPG", "status": "risk"},
            {"canonical_test_code": "LDL", "status": "risk"},
        ],
    )
    pkg = _service(db_session).build_pkg(5)
    # 결과물(1순위)이 채택됨 — record 원시 수치가 아니라 평가 결과물 기준.
    assert set(pkg.conditions) == {"type2_diabetes", "dyslipidemia"}


def test_get_pkg_endpoint_returns_pkg(client, db_session) -> None:
    _create_user(db_session, 7)
    _seed_record(db_session, 7, [("systolic_bp", "150")])

    from app.core.dependencies import get_current_user
    from app.domains.user.schemas import CurrentUser
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=7)
    try:
        res = client.get("/api/v1/pkg/7")
        assert res.status_code == 200
        data = res.json()["data"]
        assert data["conditions"] == ["hypertension"]
        assert data["id"] == "user-7"
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_get_pkg_endpoint_rejects_other_user(client, db_session) -> None:
    # IDOR 방지: 다른 사용자의 PKG를 조회하면 403
    _create_user(db_session, 8)
    _seed_record(db_session, 8, [("systolic_bp", "150")])

    from app.core.dependencies import get_current_user
    from app.domains.user.schemas import CurrentUser
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=999)
    try:
        res = client.get("/api/v1/pkg/8")  # 남의 user_id
        assert res.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_get_pkg_endpoint_404(client, db_session) -> None:
    from app.core.dependencies import get_current_user
    from app.domains.user.schemas import CurrentUser
    from app.main import app

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=999)
    try:
        res = client.get("/api/v1/pkg/999")
        assert res.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
