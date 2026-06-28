from app.domains.health_metric.schemas import HealthMetricEvaluationItem
from app.domains.mission.agents.context_builder import ContextBuilder
from app.domains.mission.agents.drafter import MissionDrafter
from app.domains.mission.agents.knowledge import KnowledgeProvider, StubKnowledgeProvider
from app.domains.mission.agents.personalizer import Personalizer
from app.domains.mission.agents.safety import SafetyValidator
from app.domains.mission.prompts import DISCLAIMER
from app.domains.mission.schemas import MissionSet


class MissionGenerator:
    """미션 생성 멀티에이전트 오케스트레이터.

    트리거를 모르는 순수 callable. 검진완료 콜백·일일 배치·`/today` lazy 생성 등
    어디서든 generate() 한 번 호출로 개인화 미션 세트를 만든다.

    파이프라인: 지식조회(KG/PKG) → 컨텍스트 → 초안(Drafter) → 안전검증(Safety)
                → 선택·경험치(Personalizer)
    """

    def __init__(
        self,
        drafter: MissionDrafter | None = None,
        safety: SafetyValidator | None = None,
        personalizer: Personalizer | None = None,
        knowledge: KnowledgeProvider | None = None,
    ) -> None:
        self.drafter = drafter or MissionDrafter()
        self.safety = safety or SafetyValidator()
        self.personalizer = personalizer or Personalizer()
        self.knowledge = knowledge or StubKnowledgeProvider()
        self.context_builder = ContextBuilder()

    async def generate(
        self,
        *,
        user_id: int,
        evaluation_results: list[HealthMetricEvaluationItem],
        sex: str | None = None,
        age: int | None = None,
        character_level: int = 1,
        recent_mission_titles: list[str] | None = None,
        recent_completion_rate: float | None = None,
        target_date: str | None = None,
        max_missions: int = 4,
    ) -> MissionSet:
        knowledge = await self.knowledge.fetch(evaluation_results)
        context = self.context_builder.build(
            user_id=user_id,
            evaluation_results=evaluation_results,
            sex=sex,
            age=age,
            character_level=character_level,
            recent_mission_titles=recent_mission_titles,
            recent_completion_rate=recent_completion_rate,
            knowledge=knowledge,
            target_date=target_date,
            max_missions=max_missions,
        )

        candidates, source = await self.drafter.draft(context)
        drafted_count = len(candidates)
        safe_candidates = await self.safety.validate(candidates)
        missions = self.personalizer.select(safe_candidates, context)

        for mission in missions:
            mission.source = source

        return MissionSet(
            status=self._status(source, drafted_count, len(safe_candidates)),
            missions=missions,
            disclaimer=DISCLAIMER,
            target_date=context.target_date,
        )

    def _status(self, source: str, drafted_count: int, safe_count: int) -> str:
        if source == "fallback":
            return "fallback"
        if safe_count < drafted_count:
            return "partial"  # LLM이 만든 후보 일부가 안전검증에서 제거됨
        return "generated"
