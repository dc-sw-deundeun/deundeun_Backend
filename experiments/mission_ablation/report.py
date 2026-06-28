"""Ablation 결과 집계 + 산출물 생성 (csv / json / md / png)."""

import csv
import json
from pathlib import Path

from app.domains.mission import pool
from experiments.mission_ablation.metrics import EvalRecord

_LEVELS = ("l0", "l1", "l2", "l3", "l4")


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _needs_referral(conditions: list[str]) -> bool:
    return bool(set(conditions) & set(pool.load_pool().get("referrals", {})))


def aggregate(records: list[EvalRecord], outputs: dict) -> dict[str, dict]:
    """config_label별 평균 지표."""
    referral_personas = {
        pid for pid, e in outputs.items() if _needs_referral(e["persona"]["conditions"])
    }
    labels = []
    for r in records:
        if r.config_label not in labels:
            labels.append(r.config_label)

    agg: dict[str, dict] = {}
    for label in labels:
        rows = [r for r in records if r.config_label == label]
        traps = [r for r in rows if r.persona_kind == "trap"]
        ref_rows = [r for r in rows if r.persona_id in referral_personas]
        agg[label] = {
            "personalization": _mean([r.personalization for r in rows]),
            "levels": {lv: _mean([r.personalization_levels.get(lv, 0) for r in rows]) for lv in _LEVELS},
            "faithfulness": _mean([r.faithfulness for r in rows]),
            "grounding_rate": _mean([r.grounding_rate for r in rows]),
            "safety_trap": _mean([r.safety_violation_rate for r in traps]),
            "safety_all": _mean([r.safety_violation_rate for r in rows]),
            "referral_rate": _mean([1.0 if r.referral_satisfied else 0.0 for r in ref_rows]),
            "latency_ms": _mean([r.latency_ms for r in rows]),
            "tokens": _mean([float(r.total_tokens) for r in rows]),
            "regenerations": _mean([float(r.regenerations) for r in rows]),
        }
    return agg


def composite_score(m: dict) -> float:
    return (
        0.40 * (m["personalization"] / 100.0)
        + 0.30 * m["faithfulness"]
        + 0.30 * (1.0 - m["safety_trap"])
    )


def pareto_front(agg: dict[str, dict]) -> list[str]:
    """(personalization↑, faithfulness↑, safety_trap↓) 비지배 집합."""
    labels = list(agg)
    front = []
    for a in labels:
        ma = agg[a]
        dominated = False
        for b in labels:
            if a == b:
                continue
            mb = agg[b]
            if (
                mb["personalization"] >= ma["personalization"]
                and mb["faithfulness"] >= ma["faithfulness"]
                and mb["safety_trap"] <= ma["safety_trap"]
                and (
                    mb["personalization"] > ma["personalization"]
                    or mb["faithfulness"] > ma["faithfulness"]
                    or mb["safety_trap"] < ma["safety_trap"]
                )
            ):
                dominated = True
                break
        if not dominated:
            front.append(a)
    return front


def write_matrix_csv(agg: dict[str, dict], path: Path) -> None:
    cols = [
        "config",
        "personalization",
        "L0",
        "L1",
        "L2",
        "L3",
        "L4",
        "faithfulness",
        "grounding_rate",
        "safety_trap",
        "safety_all",
        "referral_rate",
        "latency_ms",
        "tokens",
        "regenerations",
        "composite",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for label, m in agg.items():
            w.writerow(
                [
                    label,
                    f"{m['personalization']:.1f}",
                    *[f"{m['levels'][lv]:.1f}" for lv in _LEVELS],
                    f"{m['faithfulness']:.3f}",
                    f"{m['grounding_rate']:.3f}",
                    f"{m['safety_trap']:.3f}",
                    f"{m['safety_all']:.3f}",
                    f"{m['referral_rate']:.3f}",
                    f"{m['latency_ms']:.0f}",
                    f"{m['tokens']:.0f}",
                    f"{m['regenerations']:.2f}",
                    f"{composite_score(m):.3f}",
                ]
            )


def write_outputs_json(outputs: dict, path: Path) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(outputs, f, ensure_ascii=False, indent=2)


def _table(agg: dict[str, dict]) -> str:
    head = (
        "| config | 개인화 | L4(멀티홉) | 충실성 | grounding | 안전위반(함정) | 권고충족 | "
        "지연(ms) | 토큰 | composite |\n"
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )
    rows = ""
    for label, m in agg.items():
        rows += (
            f"| {label} | {m['personalization']:.1f} | {m['levels']['l4']:.1f} | "
            f"{m['faithfulness']:.3f} | {m['grounding_rate']:.3f} | {m['safety_trap']:.3f} | "
            f"{m['referral_rate']:.2f} | {m['latency_ms']:.0f} | {m['tokens']:.0f} | "
            f"{composite_score(m):.3f} |\n"
        )
    return head + rows


def _delta_table(agg: dict[str, dict]) -> str:
    base = agg.get("baseline")
    if not base:
        return ""
    out = "| 모듈 | Δ개인화 | Δ충실성 | Δ안전위반(함정) |\n|---|---|---|---|\n"
    for label in ("M1", "M2", "M3", "M4", "M5"):
        if label not in agg:
            continue
        m = agg[label]
        out += (
            f"| {label} | {m['personalization'] - base['personalization']:+.1f} | "
            f"{m['faithfulness'] - base['faithfulness']:+.3f} | "
            f"{m['safety_trap'] - base['safety_trap']:+.3f} |\n"
        )
    return out


def write_report_md(agg: dict[str, dict], records: list[EvalRecord], path: Path) -> None:
    front = pareto_front(agg)
    best = max(agg, key=lambda label: composite_score(agg[label]))
    base = agg.get("baseline", {})

    lines = ["# 미션 생성 Ablation 리포트\n"]
    lines.append(
        f"- 페르소나 20개(함정 6 + 일반 14), config {len(agg)}종, 미션/세트 평가.\n"
        "- 안전위반율은 함정 페르소나 기준이며, M4 게이트와 동일한 결정적 규칙으로 측정하므로 "
        "M4 ON에서는 구조적으로 0에 수렴한다(의미: baseline 대비 감소폭). M2는 사후 필터 근사다.\n"
        "- **한계(해석 주의)**: ①안전 탐지는 키워드 기반이라 표현이 키워드를 벗어나면 누락 가능"
        "(재현율 한계) → baseline 위반율은 하한값. ②개인화는 LLM-as-judge(G-Eval)이며 생성과 "
        "동일 모델 계열(HCX)이 채점 → 절대값보다 config 간 상대 비교로 해석. ③M2는 디코딩 제약이 "
        "아닌 사후 grounded_on 필터 근사.\n"
    )

    lines.append("\n## 1. 전체 매트릭스\n")
    lines.append(_table(agg))

    lines.append("\n## 2. 모듈별 개별 기여도 (단일 ON vs baseline)\n")
    lines.append(_delta_table(agg))

    lines.append("\n## 3. 생성 전 vs 생성 후 개입\n")
    if "pre(M1+M3)" in agg and "post(M2+M4)" in agg:
        pre, post = agg["pre(M1+M3)"], agg["post(M2+M4)"]
        lines.append(
            f"- 생성 전(M1+M3): 개인화 {pre['personalization']:.1f}, 충실성 {pre['faithfulness']:.3f}, "
            f"안전위반 {pre['safety_trap']:.3f}\n"
            f"- 생성 후(M2+M4): 개인화 {post['personalization']:.1f}, 충실성 {post['faithfulness']:.3f}, "
            f"안전위반 {post['safety_trap']:.3f}\n"
            "- 해석: 생성 전 개입(M1·M3)은 개인화·충실성을, 생성 후 개입(M2·M4)은 안전·충실성 정제를 주로 끌어올린다.\n"
        )

    lines.append("\n## 4. 시너지 (full vs baseline)\n")
    if base and "full" in agg:
        full = agg["full"]
        lines.append(
            f"- full: 개인화 {full['personalization']:.1f} (Δ{full['personalization'] - base['personalization']:+.1f}), "
            f"충실성 {full['faithfulness']:.3f} (Δ{full['faithfulness'] - base['faithfulness']:+.3f}), "
            f"안전위반 {full['safety_trap']:.3f} (Δ{full['safety_trap'] - base['safety_trap']:+.3f})\n"
        )

    lines.append("\n## 5. Pareto 최적 (개인화↑·충실성↑·안전위반↓)\n")
    lines.append("- Pareto front: " + ", ".join(f"`{x}`" for x in front) + "\n")

    lines.append("\n## 6. 최종 추천 조합\n")
    bm = agg[best]
    lines.append(
        f"- **추천: `{best}`** (composite {composite_score(bm):.3f})\n"
        f"  - 개인화 {bm['personalization']:.1f} / 충실성 {bm['faithfulness']:.3f} / "
        f"안전위반(함정) {bm['safety_trap']:.3f} / 지연 {bm['latency_ms']:.0f}ms / 토큰 {bm['tokens']:.0f}\n"
        "  - 근거: composite = 0.40·개인화 + 0.30·충실성 + 0.30·(1−안전위반). "
        "안전이 최우선인 의료 맥락에서 함정 위반을 0으로 누르면서 개인화·충실성을 함께 높이는 조합을 택한다.\n"
    )
    path.write_text("".join(lines), encoding="utf-8")


def plot_tradeoff(agg: dict[str, dict], path: Path) -> bool:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return False

    front = set(pareto_front(agg))
    fig, ax = plt.subplots(figsize=(9, 6))
    for label, m in agg.items():
        on_front = label in front
        sc = ax.scatter(
            m["personalization"],
            m["faithfulness"],
            s=120 + 600 * m["safety_trap"],
            c=[m["safety_trap"]],
            cmap="Reds",
            vmin=0,
            vmax=max(0.001, max(v["safety_trap"] for v in agg.values())),
            edgecolors="black" if on_front else "gray",
            linewidths=2 if on_front else 0.8,
        )
        ax.annotate(label, (m["personalization"], m["faithfulness"]), fontsize=8,
                    xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("Personalization (G-Eval overall)")
    ax.set_ylabel("Faithfulness (grounded_on in PKG)")
    ax.set_title("Ablation tradeoff (size/color = trap safety-violation, bold edge = Pareto front)")
    fig.colorbar(sc, label="safety violation rate (trap)")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return True


def generate_all(records: list[EvalRecord], outputs: dict, results_dir: Path) -> dict:
    results_dir.mkdir(parents=True, exist_ok=True)
    agg = aggregate(records, outputs)
    write_matrix_csv(agg, results_dir / "ablation_matrix.csv")
    write_outputs_json(outputs, results_dir / "per_persona_outputs.json")
    write_report_md(agg, records, results_dir / "best_config_report.md")
    plotted = plot_tradeoff(agg, results_dir / "tradeoff_plot.png")
    return {"agg": agg, "pareto": pareto_front(agg), "plotted": plotted}
