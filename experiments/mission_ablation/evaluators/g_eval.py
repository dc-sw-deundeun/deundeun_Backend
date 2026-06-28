"""G-Eval — 개인화 정도를 LLM-as-judge로 0~100 점수화(레벨 L0~L4).

L0 교과서(누구에게나 같은 일반론) / L1 수치(개인 수치 반영) / L2 약물(복약 고려) /
L3 이력(과거 이력·순응도 반영) / L4 멀티홉 인과(KG 관계 기반 인과 추론).
판정 LLM은 생성 LLM과 별도 인스턴스로 둔다. LLM이 없으면 결정적 proxy로 대체(스모크용).
"""

from app.domains.mission.agents.base import LLMClient
from app.domains.mission.pkg import InMemoryPKG
from app.domains.mission.schemas import PKG, MissionSet

_LEVELS = ("l0", "l1", "l2", "l3", "l4")

_SYSTEM = (
    "You are a strict evaluator (G-Eval) scoring how PERSONALIZED a set of daily health missions "
    "is for a specific user. Score 0-100 on each level. L0: generic textbook advice anyone could "
    "receive. L1: tailored to the user's specific metrics/numbers. L2: accounts for the user's "
    "medications. L3: accounts for the user's history/adherence (e.g., success_rate). L4: reflects "
    "multi-hop causal reasoning over the knowledge graph (condition→complication→action). Also give "
    "an overall 0-100. Generic missions must score low on L1-L4. Output strict JSON."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        **{lv: {"type": "integer"} for lv in _LEVELS},
        "overall": {"type": "integer"},
        "justification": {"type": "string"},
    },
    "required": [*_LEVELS, "overall", "justification"],
    "additionalProperties": False,
}


class GEvalJudge:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient()

    async def judge(self, pkg: PKG, ms: MissionSet) -> dict:
        client = InMemoryPKG(pkg)
        if not self.llm.has_llm:
            return self._fallback(pkg, ms, client)
        user = {
            "user": {
                "conditions": client.conditions(),
                "medications": client.medications(),
                "relations": [r.text for r in client.relations()],
                "steps_avg": client.wearable().steps_avg,
                "success_rate": client.history().success_rate,
            },
            "ideal_reference": (pkg.ground_truth.ideal if pkg.ground_truth else []),
            "missions": [
                {
                    "title": m.title,
                    "rationale": m.rationale,
                    "grounded_on": m.grounded_on,
                    "duration_min": m.execution.duration_min,
                }
                for m in ms.missions
            ],
        }
        try:
            data, _ = await self.llm.structured(_SYSTEM, user, _SCHEMA, "g_eval")
        except Exception:
            return self._fallback(pkg, ms, client)
        return data

    def _fallback(self, pkg: PKG, ms: MissionSet, client: InMemoryPKG) -> dict:
        """LLM 없을 때의 결정적 proxy(스모크 전용 — 실제 실험은 LLM 사용)."""
        meds = set(client.medications())
        text = " ".join(f"{m.title} {m.rationale}" for m in ms.missions)
        has_numbers = any(m.execution.duration_min for m in ms.missions) or any(
            ch.isdigit() for ch in text
        )
        med_aware = any(med in text for med in meds)
        grounded = sum(1 for m in ms.missions if m.grounded_on) / (len(ms.missions) or 1)
        levels = {
            "l0": 60,
            "l1": 80 if has_numbers else 40,
            "l2": 80 if med_aware else 30,
            "l3": 50,
            "l4": int(20 + 70 * grounded),
        }
        overall = int(sum(levels.values()) / len(levels))
        return {**levels, "overall": overall, "justification": "deterministic proxy (no LLM)"}
