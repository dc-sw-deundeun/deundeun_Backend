"""PKG 그래프 조립 유틸 — 노드/엣지 빌드 + 큐레이션 시드/MONDO 매핑 로더.

미션 엔진이 소비하는 PKG의 nodes/edges를 만든다. 합병증 엣지는 큐레이션 시드
(condition_edges.json)가 정본이다 — #9 KG 근거로 mission_pool 어휘에 맞춘 동반질환 지식.
엣지 스펙은 `(src_id, rel, dst_id, attrs)` 4-튜플이고, 여기서 노드로 조립한다.
노드 라벨은 `mission.pool.condition_label`(mission_pool.json)이 단일 출처 — id/label이
mission_pool 어휘와 맞아야 M2 grounding·M3 KAG가 동작한다.
condition_mondo_map은 조건 id→#9 MONDO id 정적 매핑(향후 KG 참조/문서화용)이다.
"""

import json
from functools import lru_cache
from pathlib import Path

from app.domains.mission import pool
from app.domains.mission.schemas import PkgEdge, PkgNode

_DATA = Path(__file__).parent / "data"
_EDGES_PATH = _DATA / "condition_edges.json"
_MONDO_PATH = _DATA / "condition_mondo_map.json"

# (src_id, rel, dst_id, attrs)
EdgeSpec = tuple[str, str, str, dict]


@lru_cache(maxsize=1)
def _fallback_edges() -> dict[str, list[dict]]:
    with _EDGES_PATH.open(encoding="utf-8") as f:
        return json.load(f).get("edges", {})


@lru_cache(maxsize=1)
def condition_mondo_map() -> dict[str, str]:
    """mission_pool 조건 id → #9 MONDO disease id."""
    with _MONDO_PATH.open(encoding="utf-8") as f:
        return dict(json.load(f).get("map", {}))


def condition_labels(conditions: list[str]) -> dict[str, str]:
    """조건 id → 한국어 label (mission_pool 단일 출처)."""
    return {c: pool.condition_label(c) for c in conditions}


def fallback_edge_specs(conditions: list[str]) -> list[EdgeSpec]:
    """커밋된 큐레이션 시드에서 조건별 합병증 엣지 스펙을 만든다(합병증 엣지의 정본)."""
    seed = _fallback_edges()
    specs: list[EdgeSpec] = []
    for cid in conditions:
        for edge in seed.get(cid, []):
            specs.append(
                (cid, edge.get("rel", "disease_disease"), edge["dst"], edge.get("attrs", {}))
            )
    return specs


def build_graph(
    conditions: list[str], edge_specs: list[EdgeSpec]
) -> tuple[list[PkgNode], list[PkgEdge]]:
    """조건 + 엣지 스펙 → PKG nodes/edges. endpoint는 모두 노드로 보장(한국어 label)."""
    order: list[str] = []
    nodes: dict[str, PkgNode] = {}

    def ensure(cid: str) -> None:
        if cid not in nodes:
            nodes[cid] = PkgNode(id=cid, label=pool.condition_label(cid), type="Disease")
            order.append(cid)

    for cid in conditions:
        ensure(cid)

    edges: list[PkgEdge] = []
    for src, rel, dst, attrs in edge_specs:
        ensure(src)
        ensure(dst)
        edges.append(PkgEdge(src=src, rel=rel, dst=dst, attrs=dict(attrs or {})))

    return [nodes[cid] for cid in order], edges
