"""PKG(개인 지식 그래프) 쿼리 인터페이스와 in-memory 목 구현.

실험에서는 페르소나 PKG를 메모리 그래프로 띄워 쿼리한다. 인터페이스(PKGClient)는
추후 Neo4j 구현으로 교체할 수 있도록 Protocol로 정의한다 (analysis_client 컨벤션).
"""

from typing import Protocol, runtime_checkable

from app.domains.mission.schemas import PKG, History, MetricTrend, Relation, Wearable

_MAX_HOPS = 2


def _norm(text: str) -> str:
    """grounding/노드 식별자 비교용 정규화."""
    text = text.strip()
    if "(" in text:  # "심혈관질환 (risk:high)" 같은 주석 제거
        text = text.split("(")[0]
    return text.replace(" ", "").replace("_", "").lower()


def _parse_endpoints(grounding: str) -> tuple[str, str] | None:
    """'고혈압 -[rel]-> 심혈관질환' / '고혈압→심혈관질환' → (시작, 끝) 정규화 토큰."""
    s = grounding.replace("→", "->")
    if "->" not in s:
        return None
    parts = [p for p in s.split("->") if p.strip()]
    if len(parts) < 2:
        return None
    left = parts[0].split("-[")[0]
    right = parts[-1]
    return _norm(left), _norm(right)


@runtime_checkable
class PKGClient(Protocol):
    def conditions(self) -> list[str]: ...
    def medications(self) -> list[str]: ...
    def flags(self) -> dict[str, bool]: ...
    def wearable(self) -> Wearable: ...
    def history(self) -> History: ...
    def trends(self) -> list[MetricTrend]: ...
    def relations(self, max_hops: int = _MAX_HOPS) -> list[Relation]: ...
    def edge_exists(self, grounding: str) -> bool: ...


class InMemoryPKG:
    """페르소나 PKG를 메모리 그래프로 띄워 쿼리하는 목 구현."""

    def __init__(self, pkg: PKG) -> None:
        self.pkg = pkg
        self._label = {n.id: (n.label or n.id) for n in pkg.nodes}
        # 인접 리스트: src -> [(rel, dst, attrs)]
        self._adj: dict[str, list[tuple[str, str, dict]]] = {}
        for e in pkg.edges:
            self._adj.setdefault(e.src, []).append((e.rel, e.dst, e.attrs))

    # --- 평면 조회 ---
    def conditions(self) -> list[str]:
        return [self._label.get(c, c) for c in self.pkg.conditions]

    def medications(self) -> list[str]:
        return [self._label.get(m, m) for m in self.pkg.medications]

    def flags(self) -> dict[str, bool]:
        return dict(self.pkg.flags)

    def wearable(self) -> Wearable:
        return self.pkg.wearable

    def history(self) -> History:
        return self.pkg.history

    def trends(self) -> list[MetricTrend]:
        return list(self.pkg.trends)

    def condition_ids(self) -> list[str]:
        return list(self.pkg.conditions)

    def medication_ids(self) -> list[str]:
        return list(self.pkg.medications)

    # --- M3: 관계 체인 추출 ---
    def relations(self, max_hops: int = _MAX_HOPS) -> list[Relation]:
        seeds = list(self.pkg.conditions) + list(self.pkg.medications)
        out: list[Relation] = []
        seen: set[str] = set()
        # 1-hop
        for src in seeds:
            for rel, dst, attrs in self._adj.get(src, []):
                key = f"{src}->{dst}"
                if key in seen:
                    continue
                seen.add(key)
                cite = f"{self._label.get(src, src)}->{self._label.get(dst, dst)}"
                out.append(
                    Relation(text=self._edge_text(src, rel, dst, attrs), edge=key, cite=cite)
                )
        # 2-hop (seed → mid → leaf)
        if max_hops >= 2:
            for src in seeds:
                for rel1, mid, a1 in self._adj.get(src, []):
                    for rel2, dst, a2 in self._adj.get(mid, []):
                        key = f"{src}->{mid}->{dst}"
                        if key in seen:
                            continue
                        seen.add(key)
                        text = (
                            f"{self._edge_text(src, rel1, mid, a1)} → "
                            f"{self._edge_text(mid, rel2, dst, a2)}"
                        )
                        cite = f"{self._label.get(src, src)}->{self._label.get(dst, dst)}"
                        out.append(Relation(text=text, edge=key, cite=cite))
        return out

    def _edge_text(self, src: str, rel: str, dst: str, attrs: dict) -> str:
        text = f"{self._label.get(src, src)} -[{rel}]-> {self._label.get(dst, dst)}"
        if attrs:
            text += " (" + ", ".join(f"{k}:{v}" for k, v in attrs.items()) + ")"
        return text

    # --- M2 / faithfulness: 엣지 존재 검증 ---
    def edge_exists(self, grounding: str) -> bool:
        endpoints = _parse_endpoints(grounding)
        if endpoints is None:
            return False
        start, end = endpoints
        # 직접 엣지
        for e in self.pkg.edges:
            if self._matches(e.src, start) and self._matches(e.dst, end):
                return True
        # 2-hop 경로
        for e1 in self.pkg.edges:
            if not self._matches(e1.src, start):
                continue
            for rel2, dst2, _ in self._adj.get(e1.dst, []):
                if self._matches(dst2, end):
                    return True
        return False

    def _matches(self, node_id: str, token: str) -> bool:
        return token in (_norm(node_id), _norm(self._label.get(node_id, node_id)))
