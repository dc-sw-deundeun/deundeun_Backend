"""PKG 스냅샷 영속(pkg_snapshots) — 유저당 1행 교체, 실패 시 응답 유지.

Neo4j 대신 앱 Postgres에 영속한다(#9 의학 KG와 물리 분리). db_session 픽스처
(Postgres testcontainers)만 필요 — 별도 그래프 DB 없이 검증된다.
"""

from sqlalchemy import func, select

from app.domains.pkg.models import PkgSnapshot
from app.domains.pkg.repository import PkgRepository
from tests.domains.pkg.test_service import _create_user, _seed_record, _service


def _snapshot_count(db) -> int:
    return db.scalar(select(func.count()).select_from(PkgSnapshot))


def test_build_pkg_persists_snapshot(db_session) -> None:
    _create_user(db_session, 11)
    record = _seed_record(db_session, 11, [("systolic_bp", "150"), ("fasting_glucose", "130")])

    pkg = _service(db_session).build_pkg(11)

    snapshot = PkgRepository(db_session).get_by_user(11)
    assert snapshot is not None
    assert snapshot.source_record_id == record.id
    # 저장 payload == 반환 객체 (byte-identical 스냅샷)
    assert snapshot.payload == pkg.model_dump(mode="json")
    assert snapshot.payload["conditions"] == pkg.conditions
    assert _snapshot_count(db_session) == 1


def test_rebuild_replaces_snapshot_single_row(db_session) -> None:
    _create_user(db_session, 12)
    _seed_record(db_session, 12, [("fasting_glucose", "110")])  # prediabetes
    _service(db_session).build_pkg(12)

    newer = _seed_record(db_session, 12, [("fasting_glucose", "130")])  # type2_diabetes
    _service(db_session).build_pkg(12)

    # UNIQUE(user_id) — 여전히 1행, 최신 빌드로 교체됨
    assert _snapshot_count(db_session) == 1
    snapshot = PkgRepository(db_session).get_by_user(12)
    assert snapshot is not None
    assert snapshot.source_record_id == newer.id
    assert snapshot.payload["conditions"] == ["type2_diabetes"]


def test_get_by_user_returns_none_for_unknown_user(db_session) -> None:
    assert PkgRepository(db_session).get_by_user(424242) is None


def test_persist_failure_keeps_pkg_response(db_session) -> None:
    # users 행이 없어 FK 위반 → 영속은 실패하지만 PKG 응답은 유지(graceful degrade)
    _seed_record(db_session, 13, [("systolic_bp", "150")])

    pkg = _service(db_session).build_pkg(13)

    assert pkg.conditions == ["hypertension"]
    assert _snapshot_count(db_session) == 0
