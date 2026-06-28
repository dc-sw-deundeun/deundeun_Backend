"""Ablation 실행기 — 조합 × 페르소나 실행, 평가, 캐싱.

각 셀(persona × config)에서 미션을 생성하고 5종 지표로 평가한다. LLM 호출(생성·G-Eval)
결과는 results/cache.json에 캐시해 재실행/중단복구를 지원한다.
"""

import asyncio
import json
from pathlib import Path

from app.domains.mission.agents.base import LLMClient
from app.domains.mission.agents.pipeline import MissionPipeline
from app.domains.mission.schemas import MissionSet, PipelineConfig
from experiments.mission_ablation.evaluators.deterministic import (
    evaluate_faithfulness,
    evaluate_referral,
    evaluate_safety,
)
from experiments.mission_ablation.evaluators.g_eval import GEvalJudge
from experiments.mission_ablation.metrics import EvalRecord

RESULTS_DIR = Path(__file__).parent / "results"
CACHE_PATH = RESULTS_DIR / "cache.json"
_LEVELS = ("l0", "l1", "l2", "l3", "l4")


class AblationRunner:
    def __init__(
        self,
        gen_llm: LLMClient | None = None,
        judge_llm: LLMClient | None = None,
        concurrency: int = 4,
        use_cache: bool = True,
        n_missions: int = 3,
    ) -> None:
        self.pipe = MissionPipeline(llm=gen_llm or LLMClient())
        self.judge = GEvalJudge(llm=judge_llm or LLMClient())  # 생성과 별도 인스턴스
        self.sem = asyncio.Semaphore(concurrency)
        self.use_cache = use_cache
        self.n = n_missions
        self.cache: dict = self._load_cache() if use_cache else {}
        self._done = 0

    def _load_cache(self) -> dict:
        if CACHE_PATH.exists():
            with CACHE_PATH.open(encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_cache(self) -> None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with CACHE_PATH.open("w", encoding="utf-8") as f:
            json.dump(self.cache, f, ensure_ascii=False, indent=2)

    async def _cell(self, persona, label: str, config: PipelineConfig):
        key = f"{persona.id}|{label}"
        cached = self.cache.get(key)
        if cached:
            ms = MissionSet(**cached["mission_set"])
            geval = cached["g_eval"]
        else:
            async with self.sem:
                ms = await self.pipe.generate_missions(persona, config, n=self.n)
            async with self.sem:
                geval = await self.judge.judge(persona, ms)
            self.cache[key] = {"mission_set": ms.model_dump(mode="json"), "g_eval": geval}
            self._done += 1
            if self._done % 20 == 0:
                self._save_cache()
        return ms, self._evaluate(persona, label, config, ms, geval)

    def _evaluate(self, persona, label, config, ms: MissionSet, geval: dict) -> EvalRecord:
        viol, rate, reasons = evaluate_safety(ms, persona)
        faith, grate = evaluate_faithfulness(ms, persona)
        ref = evaluate_referral(ms, persona)
        levels = {k: float(geval.get(k, 0)) for k in _LEVELS}
        return EvalRecord(
            persona_id=persona.id,
            persona_kind=persona.kind,
            config_label=label,
            config=config,
            status=ms.status,
            n_missions=len(ms.missions),
            safety_violations=viol,
            safety_violation_rate=rate,
            violation_reasons=reasons,
            faithfulness=faith,
            grounding_rate=grate,
            referral_satisfied=ref,
            personalization=float(geval.get("overall", 0)),
            personalization_levels=levels,
            diversity=float(len({m.mission_type for m in ms.missions})),
            generic_index=levels["l0"] - levels["l4"],
            rejected_count=len(ms.meta.rejected),
            latency_ms=ms.meta.latency_ms,
            total_tokens=ms.meta.total_tokens,
            llm_calls=ms.meta.llm_calls,
            regenerations=ms.meta.regenerations,
        )

    async def run(self, personas, combos: dict):
        # combos 값은 PipelineConfig 또는 (persona)->PipelineConfig 라우터
        tasks = [
            self._cell(persona, label, config(persona) if callable(config) else config)
            for label, config in combos.items()
            for persona in personas
        ]
        results = await asyncio.gather(*tasks)
        if self.use_cache:
            self._save_cache()

        by_id = {p.id: p for p in personas}
        records = [r for _, r in results]
        outputs: dict = {}
        for ms, rec in results:
            persona = by_id[rec.persona_id]
            entry = outputs.setdefault(
                persona.id,
                {
                    "persona": {
                        "id": persona.id,
                        "name": persona.name,
                        "kind": persona.kind,
                        "conditions": persona.conditions,
                        "medications": persona.medications,
                        "ground_truth": persona.ground_truth.model_dump()
                        if persona.ground_truth
                        else None,
                    },
                    "outputs": {},
                },
            )
            entry["outputs"][rec.config_label] = ms.model_dump(mode="json")
        return records, outputs
