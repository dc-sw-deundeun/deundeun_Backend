from typing import Any

from app.domains.mission.agents.base import StructuredLLMAgent
from app.domains.mission.prompts import DRAFTER_SYSTEM_PROMPT
from app.domains.mission.schemas import (
    COMPLETION_TYPES,
    MISSION_TYPES,
    MissionCandidate,
    MissionGenerationContext,
)

# LLM 없거나 실패 시 사용할 안전한 기본 미션 풀 (생활습관, 의료행위 무관)
_DEFAULT_POOL: tuple[MissionCandidate, ...] = (
    MissionCandidate(
        title="물 8잔 마시기",
        description="오늘 하루 물을 8잔 이상 나눠 마셔요.",
        mission_type="hydration",
        rationale="기본 수분 섭취 습관",
    ),
    MissionCandidate(
        title="30분 걷기",
        description="가볍게 30분 정도 걸어요.",
        mission_type="exercise",
        rationale="기본 신체활동 습관",
    ),
    MissionCandidate(
        title="채소 반찬 한 가지 이상 먹기",
        description="끼니에 채소 반찬을 하나 이상 챙겨요.",
        mission_type="diet",
        rationale="기본 식단 습관",
    ),
    MissionCandidate(
        title="자정 전에 잠자리에 들기",
        description="오늘은 자정 전에 잠자리에 들어요.",
        mission_type="sleep",
        rationale="기본 수면 습관",
    ),
    MissionCandidate(
        title="10분 심호흡·스트레칭 하기",
        description="잠깐 멈추고 10분간 심호흡과 스트레칭을 해요.",
        mission_type="stress",
        rationale="기본 스트레스 관리 습관",
    ),
)


class MissionDrafter(StructuredLLMAgent):
    """검진 근거 기반 후보 미션 초안을 만든다. LLM 불가 시 기본 풀로 fallback."""

    schema_name = "mission_candidates"

    def system_prompt(self) -> str:
        return DRAFTER_SYSTEM_PROMPT

    async def draft(self, context: MissionGenerationContext) -> tuple[list[MissionCandidate], str]:
        """후보 목록과 출처("generated"|"fallback")를 반환한다."""
        if not self.has_llm:
            return self._fallback(context), "fallback"
        try:
            data = await self.generate(self._user_input(context))
            candidates = self._parse_candidates(data)
            if not candidates:
                return self._fallback(context), "fallback"
            return candidates, "generated"
        except Exception:
            return self._fallback(context), "fallback"

    def _user_input(self, context: MissionGenerationContext) -> dict[str, Any]:
        return {
            "sex": context.sex,
            "age": context.age,
            "character_level": context.character_level,
            "max_missions": context.max_missions,
            "recent_mission_titles": context.recent_mission_titles,
            "findings": [
                {
                    "code": f.canonical_test_code,
                    "name": f.name or f.input_label,
                    "status": f.status,
                    "status_label": f.status_label,
                    "note": f.note,
                }
                for f in context.findings
            ],
            "knowledge": [k.model_dump(mode="json") for k in context.knowledge],
        }

    def _parse_candidates(self, data: dict[str, Any]) -> list[MissionCandidate]:
        candidates: list[MissionCandidate] = []
        for raw in data.get("missions", []):
            mission_type = raw.get("mission_type")
            if mission_type not in MISSION_TYPES:
                continue
            completion_type = raw.get("completion_type", "manual")
            if completion_type not in COMPLETION_TYPES:
                completion_type = "manual"
            title = (raw.get("title") or "").strip()
            description = (raw.get("description") or "").strip()
            if not title or not description:
                continue
            candidates.append(
                MissionCandidate(
                    title=title,
                    description=description,
                    mission_type=mission_type,
                    completion_type=completion_type,
                    target_finding_code=raw.get("target_finding_code"),
                    rationale=(raw.get("rationale") or "").strip(),
                )
            )
        return candidates

    def _fallback(self, context: MissionGenerationContext) -> list[MissionCandidate]:
        # 최근에 준 미션은 피하고 기본 풀에서 max_missions 만큼 고른다.
        recent = {t.strip() for t in context.recent_mission_titles}
        picked = [c for c in _DEFAULT_POOL if c.title not in recent]
        if not picked:
            picked = list(_DEFAULT_POOL)
        count = max(1, min(context.max_missions, len(picked)))
        return [c.model_copy() for c in picked[:count]]

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "missions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "mission_type": {"type": "string", "enum": list(MISSION_TYPES)},
                            "completion_type": {
                                "type": "string",
                                "enum": list(COMPLETION_TYPES),
                            },
                            "target_finding_code": {"type": ["string", "null"]},
                            "rationale": {"type": "string"},
                        },
                        "required": [
                            "title",
                            "description",
                            "mission_type",
                            "completion_type",
                            "target_finding_code",
                            "rationale",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["missions"],
            "additionalProperties": False,
        }
