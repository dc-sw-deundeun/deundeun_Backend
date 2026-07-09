"""PKG 큐레이션 — 결정론적 폴백 + 작은 GPT 추출 정제.

- deterministic_curation: 원시 KG 이웃에서 phenotypes 우선(노이즈 exposure 제외) 결정론적 요약.
- curate_facts: LLM이 추출적으로 정제(제공된 facts에서만 선택), LLM 없음/실패/빈결과 시 결정론 폴백.
"""

import asyncio

from app.domains.mission.schemas import PKG, MetricTrend
from app.domains.pkg import curation
from app.domains.pkg.neighborhood import deterministic_curation


class _FakeLLM:
    def __init__(self, facts=None, has_llm=True, raises=False):
        self._facts = facts or []
        self.has_llm = has_llm
        self._raises = raises

    async def structured(self, system, user, schema, name):
        if self._raises:
            raise RuntimeError("llm down")
        return {"facts": self._facts}, None


# --- deterministic_curation ---


def test_deterministic_curation_uses_phenotypes_and_skips_exposures() -> None:
    facts = deterministic_curation(["type2_diabetes"])
    assert facts, "당뇨는 시드에 이웃이 있어야 한다"
    joined = " ".join(facts).lower()
    # phenotype 신호(인슐린 저항성 등 원문)가 포함, 독성물질 노출은 제외
    assert "insulin resistance" in joined
    assert "agent orange" not in joined and "arsenic" not in joined


def test_deterministic_curation_empty_for_unmapped() -> None:
    assert deterministic_curation(["insomnia"]) == []  # 시드에 없는 조건


# --- curate_facts (LLM 추출 + 폴백) ---


def _pkg():
    return PKG(
        id="u1",
        conditions=["type2_diabetes"],
        trends=[MetricTrend(code="FPG", direction="up", adverse=True)],
    )


def test_curate_facts_uses_llm_output_when_present() -> None:
    llm = _FakeLLM(facts=["인슐린 저항성 경향 — 체중·허리둘레 관리"])
    out = asyncio.run(curation.curate_facts(_pkg(), llm))
    assert out == ["인슐린 저항성 경향 — 체중·허리둘레 관리"]


def test_curate_facts_falls_back_when_no_llm() -> None:
    out = asyncio.run(curation.curate_facts(_pkg(), _FakeLLM(has_llm=False)))
    assert out == deterministic_curation(["type2_diabetes"])  # 결정론 폴백


def test_curate_facts_falls_back_on_llm_error() -> None:
    out = asyncio.run(curation.curate_facts(_pkg(), _FakeLLM(raises=True)))
    assert out == deterministic_curation(["type2_diabetes"])


def test_curate_facts_falls_back_on_empty_llm_result() -> None:
    out = asyncio.run(curation.curate_facts(_pkg(), _FakeLLM(facts=[])))
    assert out == deterministic_curation(["type2_diabetes"])


def test_curate_facts_empty_when_no_kg_neighbors() -> None:
    pkg = PKG(id="u2", conditions=["insomnia"])  # 시드에 이웃 없음
    out = asyncio.run(curation.curate_facts(pkg, _FakeLLM(facts=["무언가"])))
    assert out == []  # 원시 facts가 없으면 LLM 호출 없이 빈 결과


# --- curated_facts가 컨텍스트→생성 payload까지 흐르는지 ---


def test_curated_facts_flow_to_generation_payload() -> None:
    from app.domains.mission.agents.context_agent import ContextAgent
    from app.domains.mission.agents.generator import Generator
    from app.domains.mission.pkg import InMemoryPKG
    from app.domains.mission.schemas import PipelineConfig

    pkg = PKG(id="u", conditions=["type2_diabetes"], curated_facts=["인슐린 저항성 경향"])
    ctx = ContextAgent().build(InMemoryPKG(pkg), PipelineConfig())
    assert ctx.curated_facts == ["인슐린 저항성 경향"]
    payload = Generator()._ctx_payload(ctx)
    assert payload["clinical_facts"] == ["인슐린 저항성 경향"]
