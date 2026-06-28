from app.domains.mission.policy import calculate_exp_reward
from app.domains.mission.schemas import (
    GeneratedMission,
    MissionCandidate,
    MissionGenerationContext,
)


class Personalizer:
    """안전 통과 후보 중 최종 미션을 선택하고 경험치를 배정한다(결정적).

    - 위험/주의 finding과 연결된 미션을 우선
    - 최근에 준 미션·중복 제목 제거, 가능하면 타입 다양성 확보
    - max_missions 만큼 선택, 캐릭터 레벨에 따라 경험치 가산
    """

    def select(
        self,
        candidates: list[MissionCandidate],
        context: MissionGenerationContext,
    ) -> list[GeneratedMission]:
        status_by_code = {
            f.canonical_test_code: f.status for f in context.findings if f.canonical_test_code
        }
        recent = {t.strip() for t in context.recent_mission_titles}

        ordered = sorted(
            candidates,
            key=lambda c: _finding_priority(status_by_code.get(c.target_finding_code or "")),
        )

        selected: list[MissionCandidate] = []
        seen_titles: set[str] = set()
        used_types: set[str] = set()
        # 1차: 중복/최근 제외 + 타입 다양성 우선
        for candidate in ordered:
            if len(selected) >= context.max_missions:
                break
            title = candidate.title.strip()
            if title in seen_titles or title in recent:
                continue
            if candidate.mission_type in used_types:
                continue
            selected.append(candidate)
            seen_titles.add(title)
            used_types.add(candidate.mission_type)
        # 2차: 자리가 남으면 타입 중복 허용해 채움
        if len(selected) < context.max_missions:
            for candidate in ordered:
                if len(selected) >= context.max_missions:
                    break
                title = candidate.title.strip()
                if title in seen_titles or title in recent:
                    continue
                selected.append(candidate)
                seen_titles.add(title)

        return [self._to_mission(c, context) for c in selected]

    def _to_mission(
        self, candidate: MissionCandidate, context: MissionGenerationContext
    ) -> GeneratedMission:
        exp = calculate_exp_reward(candidate.mission_type) + _level_bonus(context.character_level)
        return GeneratedMission(
            title=candidate.title,
            description=candidate.description,
            mission_type=candidate.mission_type,
            completion_type=candidate.completion_type,
            exp_reward=exp,
            target_finding_code=candidate.target_finding_code,
            rationale=candidate.rationale,
        )


def _finding_priority(status: str | None) -> int:
    return {"risk": 0, "caution": 1, "unknown": 2}.get(status or "", 3)


def _level_bonus(character_level: int) -> int:
    """레벨이 오를수록 미션당 경험치를 소폭 가산한다."""
    return max(0, character_level - 1) * 2
