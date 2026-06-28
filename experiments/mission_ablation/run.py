"""Ablation 실행 CLI.

  # 오프라인 스모크(LLM 없이 fallback+proxy로 전체 배선 검증)
  PYTHONPATH=. python -m experiments.mission_ablation.run --offline

  # 실제 실행 (OPENAI_API_KEY 필요 — .env 또는 환경변수)
  PYTHONPATH=. python -m experiments.mission_ablation.run --concurrency 6
"""

import argparse
import asyncio

from app.core.config import settings
from app.domains.mission.agents.base import LLMClient
from experiments.mission_ablation.configs import COMBOS
from experiments.mission_ablation.datasets import load_personas, validate_personas
from experiments.mission_ablation.report import composite_score, generate_all
from experiments.mission_ablation.runner import RESULTS_DIR, AblationRunner


def _select_personas(personas, spec: str):
    if spec in ("", "all"):
        return personas
    if spec == "trap":
        return [p for p in personas if p.kind == "trap"]
    if spec == "normal":
        return [p for p in personas if p.kind == "normal"]
    ids = {s.strip() for s in spec.split(",")}
    return [p for p in personas if p.id in ids]


def _select_combos(spec: str) -> dict:
    if spec in ("", "all"):
        return COMBOS
    labels = {s.strip() for s in spec.split(",")}
    return {k: v for k, v in COMBOS.items() if k in labels}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="LLM 없이 fallback+proxy로 실행(스모크)")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--n-missions", type=int, default=3)
    ap.add_argument("--gen-temperature", type=float, default=0.3)
    ap.add_argument("--provider", default=None, choices=["openai", "clova"], help="기본: settings.llm_provider")
    ap.add_argument("--combos", default="all", help="쉼표구분 라벨 또는 all")
    ap.add_argument("--personas", default="all", help="all|trap|normal|id1,id2")
    args = ap.parse_args()

    personas = load_personas()
    issues = validate_personas(personas)
    if issues:
        print("페르소나 검증 실패:")
        for i in issues:
            print("  -", i)
        raise SystemExit(1)

    personas = _select_personas(personas, args.personas)
    combos = _select_combos(args.combos)

    if args.offline:
        gen_llm = LLMClient(api_key=None)
        judge_llm = LLMClient(api_key=None)
        mode = "OFFLINE (fallback + proxy)"
    else:
        provider = args.provider or settings.llm_provider
        gen_llm = LLMClient.for_provider(provider, temperature=args.gen_temperature)
        judge_llm = LLMClient.for_provider(provider, temperature=0.0)  # 판정은 결정성 위해 0
        if not gen_llm.has_llm:
            raise SystemExit(f"{provider} API 키 미설정 — .env 확인 또는 --offline 사용")
        mode = f"{provider.upper()} (model={gen_llm.model}, gen_temp={args.gen_temperature})"

    print(f"실행: {mode} | personas={len(personas)} | combos={len(combos)} | cells={len(personas)*len(combos)}")

    runner = AblationRunner(
        gen_llm=gen_llm,
        judge_llm=judge_llm,
        concurrency=args.concurrency,
        use_cache=not args.no_cache,
        n_missions=args.n_missions,
    )
    records, outputs = asyncio.run(runner.run(personas, combos))

    if not args.offline:
        fell_back = [f"{r.persona_id}|{r.config_label}" for r in records if r.llm_calls == 0]
        if fell_back:
            print(
                f"\n⚠️  경고: {len(fell_back)}/{len(records)} 셀이 LLM 호출 없이 fallback으로 처리됨 "
                "(rate limit/오류 가능). 해당 셀 지표는 무효 — 캐시 삭제 후 재실행 권장.\n"
                f"   예: {fell_back[:8]}"
            )

    summary = generate_all(records, outputs, RESULTS_DIR)

    agg = summary["agg"]
    best = max(agg, key=lambda label: composite_score(agg[label]))
    print(f"\n완료 → {RESULTS_DIR}")
    print("  ablation_matrix.csv / per_persona_outputs.json / best_config_report.md"
          + (" / tradeoff_plot.png" if summary["plotted"] else " (plot 생략: matplotlib 없음)"))
    print(f"  Pareto front: {summary['pareto']}")
    print(f"  추천 조합: {best} (composite {composite_score(agg[best]):.3f})")


if __name__ == "__main__":
    main()
