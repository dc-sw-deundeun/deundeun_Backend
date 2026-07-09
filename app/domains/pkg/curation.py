"""PKG 큐레이션 — 작은 GPT가 외부 KG 이웃을 사람 맥락으로 추출 정제.

P0가 뽑은 원시 KG 이웃(condition_neighborhood.json)은 노이즈(희귀 증후군·환경 독성물질)가
많다. 이를 이 사람의 조건조합·추세 맥락으로 **추출적**(제공된 facts에서만 선택, 새 사실 생성
금지)으로 정제해 PKG.curated_facts로 넣는다. 생성이 이걸 grounding으로 써서 안 뻔한 미션을
만든다.

동기 build_pkg는 결정론적 기본값(deterministic_curation)을 넣고, 비동기 워커가 이 함수로
LLM 정제본으로 업그레이드한다. LLM 없음/실패/빈결과면 결정론 폴백 — PKG가 grounding 원천이라
환각을 막고(추출적), 항상 유효한 값을 보장한다.
"""

import logging
from typing import Any, Protocol

from app.domains.mission.schemas import PKG
from app.domains.pkg.neighborhood import condition_facts, deterministic_curation

logger = logging.getLogger(__name__)


class CurationLLM(Protocol):
    """curate_facts가 필요로 하는 LLM 인터페이스 — 실제 LLMClient와 테스트 목 모두 만족."""

    @property
    def has_llm(self) -> bool: ...

    async def structured(
        self, system: str, user_obj: dict[str, Any], schema: dict[str, Any], schema_name: str
    ) -> tuple[dict[str, Any], Any]: ...


_CURATION_SYSTEM = (
    "You are given raw medical knowledge-graph facts (complications/phenotypes/exposures) for a "
    "user's conditions, plus their recent checkup metric trends. Select ONLY the clinically "
    "meaningful, lifestyle-actionable points for THIS person and condense each into a short Korean "
    "clinical note usable to motivate daily lifestyle missions. Base every note strictly on the "
    "provided kg_facts — do not invent facts. IGNORE rare genetic syndromes and environmental "
    "toxin exposures. Do not diagnose or give treatment/medication instructions. Return 3-8 notes."
)
_CURATION_SCHEMA = {
    "type": "object",
    "properties": {"facts": {"type": "array", "items": {"type": "string"}}},
    "required": ["facts"],
    "additionalProperties": False,
}


async def curate_facts(pkg: PKG, llm: CurationLLM) -> list[str]:
    """원시 KG 이웃 → 이 사람 맥락의 임상 요약(curated_facts).

    KG 이웃이 없으면 빈 리스트, LLM 없음/실패/빈결과면 결정론 폴백.
    """
    raw = condition_facts(pkg.conditions)
    if not raw:
        return []
    if not llm.has_llm:
        return deterministic_curation(pkg.conditions)
    try:
        user = {
            "conditions": pkg.conditions,
            "trends": [
                {"metric": t.label or t.code, "direction": t.direction, "adverse": t.adverse}
                for t in pkg.trends
            ],
            "kg_facts": raw,
        }
        data, _usage = await llm.structured(_CURATION_SYSTEM, user, _CURATION_SCHEMA, "facts")
        facts = [f.strip() for f in data.get("facts", []) if isinstance(f, str) and f.strip()]
        return facts or deterministic_curation(pkg.conditions)
    except Exception:
        logger.warning("PKG curation via LLM failed; using deterministic fallback", exc_info=True)
        return deterministic_curation(pkg.conditions)
