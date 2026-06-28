from app.domains.health_metric.schemas import HealthMetricEvaluationItem
from app.domains.mission.schemas import KnowledgeFact, MissionGenerationContext

# 미션 근거로 삼을 판정 상태 (정상 항목은 미션 생성 대상에서 제외)
_RELEVANT_STATUSES = ("risk", "caution", "unknown")
_MAX_FINDINGS = 8


class ContextBuilder:
    """검진 판정결과·프로필·게임상태·KG 근거를 엔진 입력 컨텍스트로 조립한다(결정적)."""

    def build(
        self,
        *,
        user_id: int,
        evaluation_results: list[HealthMetricEvaluationItem],
        sex: str | None = None,
        age: int | None = None,
        character_level: int = 1,
        recent_mission_titles: list[str] | None = None,
        recent_completion_rate: float | None = None,
        knowledge: list[KnowledgeFact] | None = None,
        target_date: str | None = None,
        max_missions: int = 4,
    ) -> MissionGenerationContext:
        relevant = [r for r in evaluation_results if r.status in _RELEVANT_STATUSES]
        relevant.sort(key=lambda r: _status_priority(r.status))
        return MissionGenerationContext(
            user_id=user_id,
            sex=sex,
            age=age,
            findings=relevant[:_MAX_FINDINGS],
            character_level=character_level,
            recent_mission_titles=recent_mission_titles or [],
            recent_completion_rate=recent_completion_rate,
            knowledge=knowledge or [],
            target_date=target_date,
            max_missions=max_missions,
        )


def _status_priority(status: str) -> int:
    return {"risk": 0, "caution": 1, "unknown": 2}.get(status, 3)
