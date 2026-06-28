# 미션 생성 멀티에이전트 — M1~M5 Ablation

검진 기반 개인화 미션 생성 파이프라인에서 5개 개입 모듈(M1~M5)의 기여도를 측정하는
ablation 실험. 엔진은 `app/domains/mission`의 단일 토글 파이프라인을 그대로 구동한다
(프로덕션과 동일 엔진, config만 다름).

## 파이프라인 (4단계 직렬)

```
PKG → [Agent1 컨텍스트(M3)] → [파라미터 계산(M1)] → [Agent2·3 생성 LLM(M5)]
     → [Agent4 검증(M2·M4)+재생성] → 미션
```

| 모듈 | 개입 단계 | 시점 | 역할 | 구현 |
|------|----------|------|------|------|
| **M3** KAG | 컨텍스트 수집 | 생성 전 | KG 멀티홉 관계를 컨텍스트에 주입 | `pkg.relations()` → 프롬프트 `relations[]` |
| **M1** Template+Slot | 파라미터 계산 | 생성 전 | 강도(숫자)를 룰로 계산, LLM은 표현만 | `agents/params.py` + `mission_pool.json` |
| **M5** Structured | 생성 LLM | 생성 중 | JSON 스키마 강제 출력 | `LLMClient.structured` (json_schema strict) |
| **M2** Graph-Constrained | 검증 | 생성 후 | grounded_on이 PKG에 실재하는지 대조 | `pkg.edge_exists()` → reject·재생성 |
| **M4** 검증 게이트 | 검증 | 생성 후 | hard-constraint 위반 reject + 병원상담 강제 | `pool.check_mission()` + 재생성(≤2) |

## 실행

```bash
# 의존성 (프로덕션 deps + matplotlib)
pip install -r requirements-dev.txt -r experiments/mission_ablation/requirements-exp.txt

# 오프라인 스모크 — LLM 없이 fallback+proxy로 전체 배선 검증
PYTHONPATH=. python -m experiments.mission_ablation.run --offline --no-cache

# 실제 실행 — .env에 OPENAI_API_KEY 필요
PYTHONPATH=. python -m experiments.mission_ablation.run --concurrency 6
```

옵션: `--combos baseline,full`, `--personas trap`, `--n-missions 3`, `--gen-temperature 0.3`,
`--no-cache`. LLM 결과는 `results/cache.json`에 캐시되어 재실행/중단복구가 된다.

## 산출물 (`results/`)

- `ablation_matrix.csv` — config × 지표 전체
- `per_persona_outputs.json` — 페르소나별 생성 미션 + ground truth
- `best_config_report.md` — 모듈 기여도·시점 비교·시너지·Pareto·추천 조합
- `tradeoff_plot.png` — 개인화 vs 충실성 산점도(점 크기/색 = 함정 안전위반율, Pareto 강조)

## 평가 지표

| 지표 | 정의 | 방식 |
|------|------|------|
| Personalization (L0~L4) | 교과서/수치/약물/이력/멀티홉 인과 5단계 | G-Eval (LLM-as-judge, 0~100) |
| Faithfulness | 인용 grounded_on 중 PKG 실재 비율 (미접지 미션=0) | 결정적 (`edge_exists`) |
| Safety Violation Rate | 함정 페르소나에서 hard-constraint 위반 미션 비율 | 결정적 (`check_mission`) |
| Referral 충족 | 빈혈·신장 등 병원상담 강제 충족 | 결정적 |
| Latency / Token Cost | 미션 1세트 생성 시간 / 토큰 | 런타임 계측 |

## 테스트 데이터 — 페르소나 20개

- 함정 6 (손설계, `personas/trap_personas.json`): 신장+수분, 와파린+비타민K(시금치),
  발목부종+장시간보행, 운동금지, 심혈관+고강도, 무릎관절염+고충격. 각 ground truth(이상/금지/권고) 포함.
- 일반 14 (`personas/normal_personas.json`): 단일~복합 조건, 연령·순응도·활동량 다양.

## 한계 (리포트에 명시)

- **M2는 근사 구현**: 진짜 디코딩 제약이 아닌 사후 grounded_on 필터. 진짜 제약은 future work.
- **Safety 지표의 순환성**: M4 게이트와 안전 평가기가 동일한 결정적 규칙을 공유하므로 M4 ON에서
  위반율은 구조적으로 0에 수렴한다. 의미 있는 비교는 **baseline(M4 OFF) 대비 감소폭**.
- **키워드 기반 안전 탐지**: 금지 개념을 키워드로 탐지 → 표현이 키워드를 벗어나면 누락 가능(재현율 한계).
- **변수 통제**: 모든 생성 LLM 호출은 동일 모델·temperature 고정. 판정 LLM은 생성과 별도 인스턴스(temp 0).
- **PKG는 in-memory 목**: 인터페이스(`PKGClient`)는 추후 Neo4j 구현으로 교체 가능.
