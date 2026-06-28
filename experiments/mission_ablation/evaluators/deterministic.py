"""결정적 평가기 — faithfulness · safety · referral · latency · cost.

LLM 없이 PKG와 mission_pool 규칙만으로 계산한다.
"""

from app.domains.mission import pool
from app.domains.mission.pkg import InMemoryPKG
from app.domains.mission.schemas import PKG, MissionSet


def evaluate_safety(ms: MissionSet, pkg: PKG) -> tuple[int, float, list[str]]:
    """미션 중 hard-constraint 위반 개수·비율·사유.

    주의: M4 게이트와 동일한 pool.check_mission을 쓰므로 M4 ON에서는 구조적으로 0에
    수렴한다. 의미 있는 비교는 baseline(M4 OFF) 대비 감소폭이다.
    """
    reasons: list[str] = []
    violations = 0
    for m in ms.missions:
        r = pool.check_mission(m, pkg)
        if r:
            violations += 1
            reasons.extend(r)
    n = len(ms.missions) or 1
    return violations, violations / n, reasons


def evaluate_faithfulness(ms: MissionSet, pkg: PKG) -> tuple[float, float]:
    """(faithfulness, grounding_rate).

    faithfulness: 인용된 grounded_on 중 PKG에 실재하는 비율의 미션 평균.
      - grounded_on이 비어 근거가 전혀 없으면 그 미션의 faithfulness=0(미접지 패널티).
    grounding_rate: ≥1개의 유효 grounding을 가진 미션 비율.
    """
    if not ms.missions:
        return 0.0, 0.0
    client = InMemoryPKG(pkg)
    per_mission: list[float] = []
    grounded_count = 0
    for m in ms.missions:
        if not m.grounded_on:
            per_mission.append(0.0)
            continue
        valid = [g for g in m.grounded_on if client.edge_exists(g)]
        per_mission.append(len(valid) / len(m.grounded_on))
        if valid:
            grounded_count += 1
    faithfulness = sum(per_mission) / len(per_mission)
    grounding_rate = grounded_count / len(ms.missions)
    return faithfulness, grounding_rate


def evaluate_referral(ms: MissionSet, pkg: PKG) -> bool:
    """필요한 병원 상담 권고가 충족됐는지."""
    needed = pool.referral_topics(pkg)
    if not needed:
        return True
    return any(m.mission_type == "checkup_followup" for m in ms.missions)
