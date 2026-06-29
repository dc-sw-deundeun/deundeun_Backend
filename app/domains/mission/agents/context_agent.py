"""Agent 1 — 컨텍스트 수집 (deterministic, LLM 없음).

M3 KAG 토글:
- OFF: PKG에서 조건/약물만 평면 나열
- ON : 멀티홉 관계 체인까지 추출해 컨텍스트에 주입 (relations[])
"""

from app.domains.mission.pkg import PKGClient
from app.domains.mission.schemas import PipelineConfig, StructuredContext


class ContextAgent:
    def build(self, pkg_client: PKGClient, config: PipelineConfig) -> StructuredContext:
        history = pkg_client.history()
        ctx = StructuredContext(
            conditions=pkg_client.conditions(),
            medications=pkg_client.medications(),
            wearable=pkg_client.wearable(),
            success_rate=history.success_rate,
        )
        if config.M3_kag:
            ctx.relations = pkg_client.relations()
        return ctx
