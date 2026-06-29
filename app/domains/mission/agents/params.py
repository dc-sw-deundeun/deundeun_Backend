"""M1 — Template + Slot Filling (deterministic).

미션 강도/수치를 룰로 계산해 템플릿 슬롯에 주입한다. LLM은 이 숫자를 만들지 않고
표현(rationale)만 담당한다 — "숫자·의학 사실은 M1, LLM은 표현만"이라는 핵심 원칙.
"""

from app.domains.mission import pool
from app.domains.mission.pkg import PKGClient
from app.domains.mission.schemas import PKG, Execution, MissionCandidate

_WHEN = {"walk_after_meal": "식후", "sleep_routine": "취침 전", "light_strength": "낮 시간"}


def compute_params(template: dict, pkg_client: PKGClient, pkg: PKG) -> dict:
    slots = template.get("slots", {})
    wear = pkg_client.wearable()
    sr = pkg_client.history().success_rate
    flags = pkg_client.flags()
    params: dict = {}
    for name, spec in slots.items():
        base = spec.get("base")
        if name == "duration":
            v = int(base)
            steps = wear.steps_avg
            if steps is None or steps < 3000:
                v += 0
            elif steps < 6000:
                v += 10
            else:
                v += 20
            if flags.get("cardiovascular_risk"):
                v = min(v, 15)
            if sr is not None and sr < 0.3:
                v = max(v - 5, 5)
            params[name] = v
        elif name in ("count", "minutes", "cups"):
            v = base
            if sr is not None and sr < 0.3 and isinstance(v, int) and v > 1:
                v = max(int(v * 0.7), 1)
            params[name] = v
        elif name == "topic":
            topics = pool.referral_topics(pkg)
            params[name] = topics[0][1] if topics else base
        else:  # hour 등 고정
            params[name] = base
    return params


def _difficulty(duration_min: int | None, count: int | None) -> int:
    metric = duration_min if duration_min is not None else count
    if metric is None:
        return 1
    if metric <= 10:
        return 1
    if metric <= 20:
        return 2
    return 3


def build_seeds(
    pkg_client: PKGClient, pkg: PKG, n: int, exclude: set[str] | None = None
) -> list[MissionCandidate]:
    """페르소나에 맞고 안전한 템플릿을 골라 슬롯을 채운 seed 미션을 만든다.

    grounded_on은 비워둔다(컨텍스트 관계에서 생성 단계가 채움 → M3/M5 기여 분리).
    exclude(이미 시도한 template_id)는 건너뛰어 재생성이 새 후보를 보게 한다.
    """
    exclude = exclude or set()
    seeds: list[MissionCandidate] = []
    for t in pool.candidate_templates(pkg):
        if len(seeds) >= n:
            break
        if t["id"] in exclude:
            continue
        params = compute_params(t, pkg_client, pkg)
        title = t["template"].format(**params) if params else t["template"]
        duration = params.get("duration") or params.get("minutes")
        count = params.get("count") or params.get("cups")
        seeds.append(
            MissionCandidate(
                title=title,
                mission_type=t["type"],
                template_id=t["id"],
                execution=Execution(when=_WHEN.get(t["id"], ""), duration_min=duration),
                difficulty=_difficulty(duration, count),
            )
        )
    return seeds
