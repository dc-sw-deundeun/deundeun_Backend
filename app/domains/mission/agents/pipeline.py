"""미션 생성 파이프라인 — PipelineConfig(M1~M5) 토글 오케스트레이터.

generate_missions(pkg, config) 하나로 ablation의 모든 조합을 실행한다.
흐름: ContextAgent(M3) → Generator(M1·M5) → Verifier(M2·M4) + 재생성(≤2) → 병원상담 강제.
"""

from time import perf_counter

from app.domains.mission.agents.base import LLMClient, Usage
from app.domains.mission.agents.context_agent import ContextAgent
from app.domains.mission.agents.generator import Generator
from app.domains.mission.agents.verifier import Verifier
from app.domains.mission.pkg import InMemoryPKG
from app.domains.mission.prompts import DISCLAIMER
from app.domains.mission.schemas import (
    PKG,
    GeneratedMission,
    GenerationMeta,
    MissionCandidate,
    MissionSet,
    PipelineConfig,
)

_MAX_REGEN = 2


class MissionPipeline:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()
        self.context_agent = ContextAgent()
        self.generator = Generator(self.llm)

    async def generate_missions(self, pkg: PKG, config: PipelineConfig, n: int = 3) -> MissionSet:
        client = InMemoryPKG(pkg)
        verifier = Verifier(client)
        gating = config.M2_graph_constrained or config.M4_verify_gate

        t0 = perf_counter()
        ctx = self.context_agent.build(client, config)

        accepted: list[MissionCandidate] = []
        rejected_all: list[str] = []
        tried_ids: set[str] = set()  # 이미 시도한 template_id → 재생성 시 제외
        usage_total = Usage()
        regen = 0
        any_fallback = False
        any_success = False

        while True:
            needed = n - len(accepted)
            cands, usage, used_fallback = await self.generator.generate(
                ctx, client, pkg, config, needed, exclude=tried_ids
            )
            usage_total = usage_total.add(usage)
            any_fallback = any_fallback or used_fallback
            any_success = any_success or not used_fallback
            for c in cands:
                if c.template_id:
                    tried_ids.add(c.template_id)

            if gating:
                acc, rej = verifier.filter(cands, pkg, config)
                rejected_all += rej
            else:
                acc, rej = cands, []

            seen = {a.title for a in accepted}
            for c in acc:
                if c.title and c.title not in seen:
                    accepted.append(c)
                    seen.add(c.title)

            if len(accepted) >= n or not gating or regen >= _MAX_REGEN or not rej or used_fallback:
                break
            regen += 1

        accepted = accepted[:n]
        enough = len(accepted) >= n  # 병원상담 강제추가(정원 외) 전에 판정

        # M4: 병원 상담 강제 추가 (정원 외)
        if config.M4_verify_gate:
            accepted += verifier.referral_missions(pkg, accepted)

        # LLM 실패로 fallback을 쓴 경우를 source/status에 정직하게 반영
        if not self.llm.has_llm or (any_fallback and not any_success):
            source = "fallback"
        else:
            source = "generated"

        missions = [GeneratedMission(**{**c.model_dump(), "source": source}) for c in accepted]

        if source == "fallback":
            status = "fallback"
        elif not enough or (any_fallback and any_success):
            status = "partial"
        else:
            status = "generated"

        meta = GenerationMeta(
            latency_ms=(perf_counter() - t0) * 1000,
            prompt_tokens=usage_total.prompt_tokens,
            completion_tokens=usage_total.completion_tokens,
            total_tokens=usage_total.total_tokens,
            llm_calls=usage_total.calls,
            regenerations=regen,
            rejected=rejected_all,
        )
        return MissionSet(
            persona_id=pkg.id,
            config=config,
            status=status,
            missions=missions,
            disclaimer=DISCLAIMER,
            meta=meta,
        )
