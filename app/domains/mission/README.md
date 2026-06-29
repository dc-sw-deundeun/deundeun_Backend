# 미션 생성 엔진 — I/O 계약 (PKG 브랜치 핸드오프용)

미션 생성 엔진은 **PKG(개인 지식그래프) 하나를 입력으로 받아** 개인화 미션 세트를 만든다.
PKG가 어디서/어떻게 만들어지는지는 전혀 모른다(별도 API·다중 호출자 가능). 트리거(검진완료
콜백·일일 배치·`/today` lazy 생성)도 모르는 **순수 callable**이다.

```
[PKG 생성: 별도 브랜치/API]  ──▶  PKG  ──▶  MissionPipeline.generate_missions(pkg, config)  ──▶  MissionSet
```

## 진입점

```python
from app.domains.mission.agents.base import LLMClient
from app.domains.mission.agents.pipeline import MissionPipeline
from app.domains.mission.schemas import PKG, PipelineConfig

pipe = MissionPipeline(llm=LLMClient.for_provider("clova"))   # 또는 "openai"
mission_set = await pipe.generate_missions(pkg, PipelineConfig(...), n=3)
```

## 입력 — `PKG` (schemas.py)

| 필드 | 타입 | 설명 |
|---|---|---|
| `id` | str | 식별자 (예: `"user-7"`). 출력 `persona_id`로 echo |
| `demographics` | {`age`:int?, `sex`:str?} | |
| `conditions` | [str] | **canonical id** (mission_pool 어휘: `hypertension`,`type2_diabetes`,`ckd`,`anemia`,`dyslipidemia`,`obesity`,`fatty_liver`,`ankle_edema`,`osteoarthritis`,`cardiovascular_disease`,`insomnia`,`depression_screen`,`gout`,`gerd`,`prediabetes`) |
| `medications` | [str] | canonical id (`amlodipine`,`warfarin`,`metformin`,`statin`,`diuretic`) |
| `wearable` | {`steps_avg`:int?, `resting_hr`:int?, `sleep_hours_avg`:float?} | M1 강도 계산에 사용 |
| `history` | {`success_rate`:float?, `recent_mission_titles`:[str]} | 난이도·반복회피 |
| `nodes` | [{`id`,`label`,`type`}] | type ∈ Disease·Drug·Effect·Lifestyle·Metric |
| `edges` | [{`src`,`rel`,`dst`,`attrs`}] | rel 예: `disease_disease`·`drug_effect`·`CORRELATES_WITH`. **M3(KAG)·M2(grounding)의 근거** |
| `flags` | {str:bool} | `cardiovascular_risk`,`exercise_prohibited` 등 (안전 라우팅) |
| `ground_truth` | obj? | 평가 전용 — **프로덕션 PKG엔 불필요(null)** |

> condition/medication id, edge가 mission_pool 어휘와 맞아야 M1 안전·M2 grounding이 동작한다.
> 매핑 표는 `data/mission_pool.json` 참고.

## 출력 — `MissionSet` (schemas.py)

```jsonc
{
  "persona_id": "user-7",
  "config": { "M1_template": true, ... },
  "status": "generated | partial | fallback",
  "missions": [{
    "title": "식후 15분 걷기",
    "rationale": "...",
    "grounded_on": ["고혈압->심혈관질환"],   // M2로 검증된 PKG 엣지 인용
    "execution": {"when": "식후", "duration_min": 15},
    "difficulty": 2,
    "mission_type": "exercise",              // diet|exercise|hydration|sleep|stress|checkup_followup|habit
    "template_id": "walk_after_meal",
    "source": "generated | fallback"
  }],
  "disclaimer": "...",
  "meta": {"latency_ms": 4204, "total_tokens": 592, "llm_calls": 1, "regenerations": 0, "rejected": []}
}
```

## PKG를 객체 대신 "서비스"로 줄 경우 (권장 확장점)

엔진 내부는 PKG 쿼리를 `PKGClient` Protocol(`pkg.py`)로 추상화한다. 현재 구현은
`InMemoryPKG`(PKG 객체 래핑). PKG가 원격 API/Neo4j면 **같은 Protocol을 구현**해 끼우면
엔진 무수정으로 동작한다.

```python
class PKGClient(Protocol):
    def conditions(self) -> list[str]: ...
    def medications(self) -> list[str]: ...
    def flags(self) -> dict[str, bool]: ...
    def wearable(self) -> Wearable: ...
    def history(self) -> History: ...
    def relations(self, max_hops=2) -> list[Relation]: ...   # M3
    def edge_exists(self, grounding: str) -> bool: ...        # M2 / faithfulness
```

## 설정 — `PipelineConfig` (M1~M5 토글)

`M1_template`(안전 템플릿+슬롯) · `M3_kag`(KG 관계 주입) · `M5_structured`(구조화 출력) ·
`M2_graph_constrained`(grounding 검증) · `M4_verify_gate`(안전 게이트+재생성).

> ablation 결론(연구 브랜치): 최적은 `M1+M3+M5`(게이트 없음). M1 안전 템플릿이 안전을 내재화하므로
> 사후 게이트(M2·M4)는 over-refusal·비용만 더한다. 미지 금기 방어가 필요하면 위험군만 게이트(risk_routed).
