"""엣지 시드·MONDO 매핑 정합성 + 그래프 조립 (순수 단위 테스트)."""

from app.domains.mission import pool
from app.domains.pkg import graph


def _condition_vocab() -> set[str]:
    return set(pool.load_pool().get("conditions", {}).keys())


def test_fallback_edges_use_mission_pool_vocab() -> None:
    vocab = _condition_vocab()
    seed = graph._fallback_edges()
    for src, edges in seed.items():
        assert src in vocab, f"seed src '{src}' not in mission_pool"
        for edge in edges:
            assert edge["dst"] in vocab, f"seed dst '{edge['dst']}' not in mission_pool"


def test_condition_mondo_map_keys_in_vocab() -> None:
    vocab = _condition_vocab()
    for cid in graph.condition_mondo_map():
        assert cid in vocab, f"mondo map key '{cid}' not in mission_pool"


def test_condition_mondo_map_matches_kg_mapping_table() -> None:
    """MONDO id가 #9 kg/mappings/mapping_table.json의 실제 값과 일치하는지 (있을 때만)."""
    import json
    from pathlib import Path

    table_path = Path("kg/mappings/mapping_table.json")
    if not table_path.exists():
        import pytest

        pytest.skip("kg/mappings/mapping_table.json 미존재(로컬 #9 워크스페이스 없음)")
    known = {
        m["mondo_id"]
        for m in json.loads(table_path.read_text(encoding="utf-8"))["mappings"]
        if m.get("mondo_id")
    }
    for cid, mondo in graph.condition_mondo_map().items():
        assert mondo in known, f"{cid} → {mondo} not found in #9 mapping_table"


def test_build_graph_nodes_have_korean_labels_and_edges_resolve() -> None:
    conditions = ["hypertension", "type2_diabetes"]
    specs = graph.fallback_edge_specs(conditions)
    nodes, edges = graph.build_graph(conditions, specs)

    node_ids = {n.id for n in nodes}
    # 조건 노드 + 엣지 endpoint 노드 모두 존재
    assert {"hypertension", "type2_diabetes"} <= node_ids
    for e in edges:
        assert e.src in node_ids and e.dst in node_ids
    # 라벨은 한국어(mission_pool) 단일 출처
    labels = {n.id: n.label for n in nodes}
    assert labels["hypertension"] == "고혈압"
    assert all(n.label for n in nodes)
    assert all(n.type == "Disease" for n in nodes)


def test_hypertension_grounds_to_cardiovascular_disease() -> None:
    specs = graph.fallback_edge_specs(["hypertension"])
    dsts = {dst for _src, _rel, dst, _attrs in specs}
    assert "cardiovascular_disease" in dsts
