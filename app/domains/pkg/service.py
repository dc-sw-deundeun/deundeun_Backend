"""PKG(개인 지식그래프) 조립 서비스.

검진 데이터에서 조건/플래그를 도출(adapter)하고 큐레이션 시드(condition_edges.json)로
합병증 엣지를 조립해 미션 엔진 계약(app.domains.mission.schemas.PKG)에 맞는 객체를 반환한다.
결과는 앱 Postgres(pkg_snapshots)에 유저당 1행 스냅샷으로 영속한다 — 외부 의학 KG(#9,
read-only Neo4j 아티팩트)와 물리적으로 분리되어 KG 재배포/재시드에도 개인 데이터가 안전하다.
영속이 실패해도 PKG 응답은 유지한다(경고 로그 후 폴스루).
"""

import logging

from app.core.exceptions import NotFoundException
from app.domains.analysis.repository import AnalysisRepository
from app.domains.health_metric.repository import HealthMetricAnalysisRepository
from app.domains.mission.schemas import PKG, Demographics
from app.domains.pkg import graph
from app.domains.pkg.adapter import (
    MetricReading,
    derive_conditions_and_flags,
    derive_from_evaluated,
)
from app.domains.pkg.repository import PkgRepository
from app.domains.record.repository import RecordRepository

logger = logging.getLogger(__name__)


class PkgService:
    def __init__(
        self,
        record_repo: RecordRepository,
        analysis_repo: AnalysisRepository,
        hm_analysis_repo: HealthMetricAnalysisRepository,
        pkg_repo: PkgRepository,
    ) -> None:
        self._record_repo = record_repo
        self._analysis_repo = analysis_repo
        self._hm_analysis_repo = hm_analysis_repo
        self._pkg_repo = pkg_repo

    def build_pkg(self, user_id: int) -> PKG:
        record = self._record_repo.get_latest_verified_record(user_id)
        if record is None:
            raise NotFoundException(message="검증된 검진 기록이 없습니다.")

        summary = self._analysis_repo.find_summary_by_record_id(record.id)
        risk_level = summary.risk_level if summary is not None else None

        # 1순위: health_metric 평가 결과물(canonical_test_code+status)에서 도출.
        # 없으면 record.CheckupMetricResult 원시 수치를 동일 룰엔진으로 재평가(폴백).
        hm_analysis = self._hm_analysis_repo.get_latest_for_record(record.id, user_id)
        if hm_analysis is not None and hm_analysis.results_payload:
            conditions, flags = derive_from_evaluated(
                hm_analysis.results_payload, risk_level=risk_level
            )
        else:
            metrics = self._record_repo.list_metrics(record.id)
            conditions, flags = derive_conditions_and_flags(
                [MetricReading(metric_code=m.metric_code, value=m.value) for m in metrics],
                risk_level=risk_level,
            )

        # 합병증(grounding) 엣지는 큐레이션 시드가 정본 — #9 적재본엔 disease_disease
        # 관계가 없어 라이브 조인이 늘 빈 결과였고, 시드가 #9 근거로 mission_pool 어휘에
        # 맞춘 동반질환 지식을 담는다.
        edge_specs = graph.fallback_edge_specs(conditions)
        nodes, edges = graph.build_graph(conditions, edge_specs)

        pkg = PKG(
            id=f"user-{user_id}",
            demographics=Demographics(),
            conditions=conditions,
            medications=[],  # v1: 앱에 약 소스 없음 (약 기반 회피는 mission_pool이 담당)
            nodes=nodes,
            edges=edges,
            flags=flags,
        )
        self._persist_snapshot(user_id, pkg, record.id)
        return pkg

    def _persist_snapshot(self, user_id: int, pkg: PKG, record_id: int) -> None:
        """스냅샷 영속(유저당 1행 교체). 실패해도 PKG 응답은 유지한다."""
        try:
            self._pkg_repo.upsert_snapshot(
                user_id,
                payload=pkg.model_dump(mode="json"),
                source_record_id=record_id,
            )
            self._pkg_repo.db.commit()
        except Exception:
            self._pkg_repo.db.rollback()
            logger.warning(
                "PKG snapshot persist failed; returning unpersisted PKG",
                exc_info=True,
            )
