"""Agent 4 — 검증 (deterministic). 생성 LLM과 독립(echo chamber 방지).

- M2 Graph-Constrained(근사): grounded_on의 각 관계가 PKG에 실재하는지 대조. 없으면 reject.
  ※ 진짜 디코딩 제약이 아닌 사후 필터 근사 — 리포트에 명시.
- M4 검증 게이트: mission_pool의 hard-constraint 위반 reject + 빈혈/신장 등 병원상담 강제.
재생성은 pipeline이 generator를 다시 호출해 수행한다.
"""

from app.domains.mission import pool
from app.domains.mission.pkg import PKGClient
from app.domains.mission.schemas import (
    PKG,
    Execution,
    GeneratedMission,
    MissionCandidate,
    PipelineConfig,
)


class Verifier:
    def __init__(self, pkg_client: PKGClient) -> None:
        self.pkg_client = pkg_client

    def filter(
        self, missions: list[MissionCandidate], pkg: PKG, config: PipelineConfig
    ) -> tuple[list[MissionCandidate], list[str]]:
        accepted: list[MissionCandidate] = []
        rejected: list[str] = []
        for m in missions:
            reasons: list[str] = []
            if config.M4_verify_gate:
                reasons += pool.check_mission(_as_generated(m), pkg)
            if config.M2_graph_constrained and m.grounded_on:
                if any(not self.pkg_client.edge_exists(g) for g in m.grounded_on):
                    reasons.append("grounded_on에 PKG에 없는 관계 포함(M2)")
            if reasons:
                rejected.append(m.title)
            else:
                accepted.append(m)
        return accepted, rejected

    def referral_missions(
        self, pkg: PKG, existing: list[MissionCandidate]
    ) -> list[MissionCandidate]:
        if any(m.mission_type == "checkup_followup" for m in existing):
            return []
        topics = pool.referral_topics(pkg)
        if not topics:
            return []
        _, topic = topics[0]
        return [
            MissionCandidate(
                title=f"가까운 시일 내 병원에서 {topic} 상담받기",
                rationale="검진 결과상 전문가 확인이 권장되는 항목이 있어 추가했습니다.",
                mission_type="checkup_followup",
                template_id="clinic_followup",
                execution=Execution(),
            )
        ]


def _as_generated(c: MissionCandidate) -> GeneratedMission:
    return GeneratedMission(**c.model_dump())
