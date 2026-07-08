"""mission_pool.json 로더 + hard-constraint(안전 제약) 엔진.

M4 검증 게이트와 Safety Violation 평가기가 동일한 규칙을 쓰도록 한곳에 모은다.
(주의: 게이트와 평가기가 같은 규칙을 공유하므로 M4 ON에서 위반율은 구조적으로 0에
가깝다 — 의미 있는 비교는 baseline(M4 OFF) 대비 감소폭. 키워드 기반 탐지의 한계는
M2와 마찬가지로 리포트에 명시한다.)
"""

import json
from functools import lru_cache
from pathlib import Path

from app.domains.mission.schemas import PKG, GeneratedMission

_POOL_PATH = Path(__file__).parent / "data" / "mission_pool.json"

# 자유생성 허용 타입 — type_exclusions 규칙이 없고 안전 표면이 작아, 카테고리만 유지한 채
# LLM이 미션 내용을 자유생성해도 되는 저위험 타입. 나머지(운동·식단·수분·수면·병원)는
# 수치·금기 위험이 있어 템플릿을 유지한다. concept_exclusions 키워드 게이트는 자유생성분에도
# 그대로 적용되므로 백스톱은 유지된다.
FREE_ELIGIBLE_TYPES = frozenset({"habit", "stress"})


@lru_cache(maxsize=1)
def load_pool() -> dict:
    with _POOL_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def condition_label(cid: str) -> str:
    return load_pool().get("conditions", {}).get(cid, {}).get("label", cid)


def medication_label(mid: str) -> str:
    return load_pool().get("medications", {}).get(mid, {}).get("label", mid)


def templates() -> list[dict]:
    return load_pool().get("templates", [])


def _template_excluded_for(template: dict, pkg: PKG) -> bool:
    """구조화 경로용 — 템플릿 자체가 이 페르소나에게 금지인지."""
    for reason in check_mission(
        GeneratedMission(
            title=template.get("template", ""),
            mission_type=template.get("type", ""),
            template_id=template.get("id"),
        ),
        pkg,
    ):
        if reason:
            return True
    return False


def candidate_templates(pkg: PKG) -> list[dict]:
    """페르소나 조건에 맞고 안전한 템플릿을 타깃 적합도 순으로 반환."""
    conds = set(pkg.conditions)
    scored: list[tuple[int, dict]] = []
    for t in templates():
        if _template_excluded_for(t, pkg):
            continue
        overlap = len(conds & set(t.get("targets", [])))
        scored.append((overlap, t))
    scored.sort(key=lambda x: -x[0])
    return [t for _, t in scored]


def referral_topics(pkg: PKG) -> list[tuple[str, str]]:
    """병원 상담 권고가 필요한 (condition, topic) 목록."""
    referrals = load_pool().get("referrals", {})
    return [(c, referrals[c]) for c in pkg.conditions if c in referrals]


def _active_type_exclusions(pkg: PKG) -> list[dict]:
    out = []
    for ex in load_pool().get("type_exclusions", []):
        by = ex.get("excluded_by", {})
        if _triggered(by, pkg):
            out.append(ex)
    return out


def _active_concept_exclusions(pkg: PKG) -> list[dict]:
    out = []
    for ex in load_pool().get("concept_exclusions", []):
        if _triggered(ex.get("excluded_by", {}), pkg):
            out.append(ex)
    return out


def _triggered(excluded_by: dict, pkg: PKG) -> bool:
    if set(excluded_by.get("conditions", [])) & set(pkg.conditions):
        return True
    if set(excluded_by.get("medications", [])) & set(pkg.medications):
        return True
    flags = pkg.flags
    return any(flags.get(f) for f in excluded_by.get("flags", []))


def check_mission(mission: GeneratedMission, pkg: PKG) -> list[str]:
    """미션이 페르소나의 hard-constraint를 위반하면 사유 목록을, 안전하면 [] 반환."""
    reasons: list[str] = []
    text = f"{mission.title} {mission.rationale} {mission.execution.when}"
    if mission.execution.duration_min:
        text += f" {mission.execution.duration_min}분"

    for ex in _active_type_exclusions(pkg):
        if mission.mission_type in ex.get("types", []):
            reasons.append(ex.get("reason", "type_excluded"))

    for ex in _active_concept_exclusions(pkg):
        if any(kw in text for kw in ex.get("keywords", [])):
            reasons.append(ex.get("reason", ex.get("concept", "concept_excluded")))

    return reasons


def is_safe(mission: GeneratedMission, pkg: PKG) -> bool:
    return not check_mission(mission, pkg)


def has_active_constraints(pkg: PKG) -> bool:
    """PKG 내용만으로 '위험군'인지 판정(오라클 라벨 없이) — 라우팅용.

    금기(타입/개념 제외)가 활성이거나, 병원상담이 필요하거나, 위험 플래그가 있으면 True.
    """
    if _active_type_exclusions(pkg) or _active_concept_exclusions(pkg):
        return True
    if referral_topics(pkg):
        return True
    return bool(pkg.flags.get("cardiovascular_risk") or pkg.flags.get("exercise_prohibited"))
