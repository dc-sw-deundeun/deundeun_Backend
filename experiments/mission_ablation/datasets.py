"""페르소나 데이터셋 로더 + 검증.

personas/ 의 trap_personas.json(함정 6, 손설계) + normal_personas.json(일반 14, 큐레이션)
을 PKG로 로드하고, mission_pool 어휘와 정합성을 검증한다.
"""

import json
from pathlib import Path

from app.domains.mission import pool
from app.domains.mission.schemas import PKG

_PERSONA_DIR = Path(__file__).parent / "personas"
_FILES = ["trap_personas.json", "normal_personas.json"]


def load_personas() -> list[PKG]:
    personas: list[PKG] = []
    for fname in _FILES:
        path = _PERSONA_DIR / fname
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for raw in json.load(f):
                personas.append(PKG(**raw))
    return personas


def validate_personas(personas: list[PKG]) -> list[str]:
    """정합성 이슈 목록을 반환(빈 리스트면 통과)."""
    issues: list[str] = []
    p = pool.load_pool()
    cond_vocab = set(p.get("conditions", {}))
    med_vocab = set(p.get("medications", {}))
    referrals = set(p.get("referrals", {}))

    seen: set[str] = set()
    for persona in personas:
        pid = persona.id
        if pid in seen:
            issues.append(f"[{pid}] 중복 id")
        seen.add(pid)

        for c in persona.conditions:
            if c not in cond_vocab:
                issues.append(f"[{pid}] 알 수 없는 condition: {c}")
        for m in persona.medications:
            if m not in med_vocab:
                issues.append(f"[{pid}] 알 수 없는 medication: {m}")

        node_ids = {n.id for n in persona.nodes}
        for e in persona.edges:
            if e.src not in node_ids:
                issues.append(f"[{pid}] edge.src 노드 없음: {e.src}")
            if e.dst not in node_ids:
                issues.append(f"[{pid}] edge.dst 노드 없음: {e.dst}")

        gt = persona.ground_truth
        if persona.kind == "trap":
            if gt is None or not gt.forbidden:
                issues.append(f"[{pid}] 함정 페르소나인데 ground_truth.forbidden 없음")
        # referral 정합성(경고성)
        ref_conds = [c for c in persona.conditions if c in referrals]
        if ref_conds and (gt is None or not gt.required_referrals):
            issues.append(
                f"[{pid}] referral 조건({ref_conds}) 보유인데 required_referrals 비어있음"
            )

    n = len(personas)
    if n != 20:
        issues.append(f"페르소나 수가 20이 아님: {n}")
    traps = sum(1 for x in personas if x.kind == "trap")
    if traps != 6:
        issues.append(f"함정 페르소나 수가 6이 아님: {traps}")
    return issues
