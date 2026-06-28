from typing import Any

from app.domains.mission.agents.base import StructuredLLMAgent
from app.domains.mission.prompts import BANNED_SUBSTRINGS, SAFETY_SYSTEM_PROMPT
from app.domains.mission.schemas import MISSION_TYPES, MissionCandidate


def is_safe(candidate: MissionCandidate) -> bool:
    """결정적 안전 백스톱 — 의료행위 지시/금지문구 포함 여부와 허용 타입을 검사한다.

    LLM 판정과 무관하게 항상 적용되는 하드 가드레일이다.
    """
    if candidate.mission_type not in MISSION_TYPES:
        return False
    text = f"{candidate.title} {candidate.description}"
    return not any(banned in text for banned in BANNED_SUBSTRINGS)


class SafetyValidator(StructuredLLMAgent):
    """후보 미션의 안전성을 검증한다. 결정적 백스톱 통과분에 LLM 검토를 더한다."""

    schema_name = "safety_verdicts"

    def system_prompt(self) -> str:
        return SAFETY_SYSTEM_PROMPT

    async def validate(self, candidates: list[MissionCandidate]) -> list[MissionCandidate]:
        # 1) 결정적 백스톱 — 항상 적용
        screened = [c for c in candidates if is_safe(c)]
        if not screened or not self.has_llm:
            return screened

        # 2) LLM 검토 — 거부/수정 반영, 실패 시 결정적 결과를 그대로 사용
        try:
            data = await self.generate(self._user_input(screened))
        except Exception:
            return screened

        verdicts = {
            (v.get("title") or "").strip(): v for v in data.get("verdicts", [])
        }
        approved: list[MissionCandidate] = []
        for candidate in screened:
            verdict = verdicts.get(candidate.title.strip())
            if verdict is None:
                approved.append(candidate)  # 판정 누락분은 백스톱 통과분이므로 유지
                continue
            if not verdict.get("approved", True):
                continue
            revised = self._apply_revision(candidate, verdict)
            if is_safe(revised):  # 수정문도 백스톱 재검사
                approved.append(revised)
        return approved

    def _apply_revision(
        self, candidate: MissionCandidate, verdict: dict[str, Any]
    ) -> MissionCandidate:
        title = (verdict.get("revised_title") or "").strip() or candidate.title
        description = (verdict.get("revised_description") or "").strip() or candidate.description
        return candidate.model_copy(update={"title": title, "description": description})

    def _user_input(self, candidates: list[MissionCandidate]) -> dict[str, Any]:
        return {
            "missions": [
                {
                    "title": c.title,
                    "description": c.description,
                    "mission_type": c.mission_type,
                }
                for c in candidates
            ]
        }

    def response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "verdicts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "approved": {"type": "boolean"},
                            "reason": {"type": "string"},
                            "revised_title": {"type": ["string", "null"]},
                            "revised_description": {"type": ["string", "null"]},
                        },
                        "required": [
                            "title",
                            "approved",
                            "reason",
                            "revised_title",
                            "revised_description",
                        ],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["verdicts"],
            "additionalProperties": False,
        }
