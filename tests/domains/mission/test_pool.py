"""mission_pool.json 템플릿 풀 유효성 + 조건별 커버리지(개인화 다양성).

- 구조 유효성: 신규 템플릿이 잘못 들어와도(타입 오타·잘못된 target·슬롯/플레이스홀더 불일치)
  잡아내는 영구 가드.
- 커버리지 플로어: 주요 조건별로 '조건 매칭' 템플릿이 충분한지 — 확장 전엔 실패(red),
  확장 후 통과(green). 개인화가 소수 템플릿 돌려막기로 떨어지는 걸 방지.
"""

import re

from app.domains.mission import pool
from app.domains.mission.schemas import MISSION_TYPES


def _matched_count(condition: str) -> int:
    return sum(1 for t in pool.templates() if condition in t.get("targets", []))


def test_mission_pool_templates_are_structurally_valid() -> None:
    data = pool.load_pool()
    condition_ids = set(data.get("conditions", {}))
    valid_types = set(MISSION_TYPES)
    seen_ids: set[str] = set()

    for t in data.get("templates", []):
        tid = t.get("id")
        assert tid and tid not in seen_ids, f"중복/누락 id: {tid}"
        seen_ids.add(tid)
        assert t.get("type") in valid_types, f"{tid}: 잘못된 type {t.get('type')}"
        for cond in t.get("targets", []):
            assert cond in condition_ids, f"{tid}: 미등록 target {cond}"
        # template의 {placeholder}와 slots 키가 정확히 일치해야 format이 안 깨진다
        placeholders = set(re.findall(r"{(\w+)}", t.get("template", "")))
        assert placeholders == set(t.get("slots", {})), f"{tid}: placeholder/slot 불일치"


def test_common_conditions_have_enough_matched_templates() -> None:
    """주요 조건별 '조건 매칭'(targets 포함) 템플릿 최소 개수 — 확장 전엔 부족해 실패한다."""
    for cond in ("hypertension", "type2_diabetes", "obesity", "insomnia", "depression_screen"):
        count = _matched_count(cond)
        assert count >= 5, f"{cond}: 조건 매칭 템플릿 {count}개(<5) — 개인화 다양성 부족"


def test_every_registered_condition_has_at_least_one_matched_template() -> None:
    """등록된 모든 condition은 최소 1개 이상의 조건 매칭 템플릿을 가져야 한다.

    조건은 있는데 관련 미션이 0인 유저(발목부종·무릎관절염 등)를 방지하는 불변식.
    새 condition을 대응 템플릿 없이 추가/머지하는 걸 잡는다(CodeRabbit).
    """
    condition_ids = pool.load_pool().get("conditions", {})
    uncovered = [c for c in condition_ids if _matched_count(c) == 0]
    assert uncovered == [], f"조건 매칭 템플릿이 0개인 condition: {uncovered}"
