from typing import Protocol, runtime_checkable

from app.domains.health_metric.schemas import HealthMetricEvaluationItem
from app.domains.mission.schemas import KnowledgeFact


@runtime_checkable
class KnowledgeProvider(Protocol):
    """미션 근거(권장행동·금기) 공급자.

    실제 구현은 외부 의학 KG(Neo4j)와 개인 PKG를 조인해 finding별 근거를 반환한다.
    (analysis_client의 Protocol+Stub 컨벤션과 동일)
    """

    async def fetch(self, findings: list[HealthMetricEvaluationItem]) -> list[KnowledgeFact]: ...


class StubKnowledgeProvider:
    """KG/PKG 미구축 단계용 Stub.

    빈 근거를 반환하므로 엔진은 KG 없이도 동작한다. KG·PKG 구축 후 Neo4j 기반
    구현으로 교체하고 통합 테스트한다.
    """

    async def fetch(self, findings: list[HealthMetricEvaluationItem]) -> list[KnowledgeFact]:
        return []
