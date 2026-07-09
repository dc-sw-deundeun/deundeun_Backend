"""Agent 2·3 — 미션 생성 LLM.

토글 조합:
- M1 ON  : seed(제목·수치 고정)를 받아 rationale·grounded_on만 채움
- M1 OFF : 컨텍스트로부터 미션 전체를 생성(수치 포함 → 할루시네이션 위험)
- M5 ON  : JSON 스키마 강제 출력
- M5 OFF : 자유 텍스트 → best-effort 파싱(구조 약함)
LLM이 없으면(키 없음/실패) 결정적 fallback 미션을 만든다.
"""

import re
from typing import Any

from app.domains.mission import policy, pool, prompts
from app.domains.mission.agents.base import LLMClient, Usage
from app.domains.mission.agents.params import build_seeds
from app.domains.mission.pkg import PKGClient
from app.domains.mission.schemas import (
    MISSION_TYPES,
    PKG,
    Execution,
    MissionCandidate,
    PipelineConfig,
    StructuredContext,
)

_ARROW = re.compile(r"(\S+\s*(?:->|→)\s*\S+)")

# LLM이 enum 대신 한국어/변형 타입을 줄 때 매핑
_TYPE_KEYWORDS = {
    "exercise": ("운동", "걷기", "유산소", "근력", "스쿼트", "산책", "스트레칭"),
    "diet": ("식습관", "식단", "식이", "저염", "채소", "영양", "음식", "당"),
    "hydration": ("수분", "물"),
    "sleep": ("수면", "취침", "잠"),
    "stress": ("스트레스", "심호흡", "명상", "이완"),
    "checkup_followup": ("상담", "병원", "진료", "검진", "추적", "재검"),
    "habit": ("기록", "습관"),
}


def _normalize_type(raw: str, title: str = "") -> str:
    if raw in MISSION_TYPES:
        return raw
    text = f"{raw} {title}"
    for mtype, kws in _TYPE_KEYWORDS.items():
        if any(kw in text for kw in kws):
            return mtype
    return "habit"


class Generator:
    def __init__(self, llm: LLMClient | None = None) -> None:
        self.llm = llm or LLMClient.for_provider()

    async def generate(
        self,
        ctx: StructuredContext,
        pkg_client: PKGClient,
        pkg: PKG,
        config: PipelineConfig,
        n: int,
        exclude: set[str] | None = None,
    ) -> tuple[list[MissionCandidate], Usage, bool]:
        """(candidates, usage, used_fallback) 반환. used_fallback=True면 LLM 미사용/실패로
        결정적 fallback을 쓴 것 — 상위(pipeline)가 source/status를 정확히 기록하도록 신호."""
        seeds = build_seeds(pkg_client, pkg, n, exclude) if config.M1_template else None

        if not self.llm.has_llm:
            return self._fallback(seeds, pkg, n, exclude), Usage(), True

        try:
            if config.M1_template:
                cands, usage = await self._generate_seeded(ctx, seeds or [], config)
            else:
                cands, usage = await self._generate_full(ctx, config, n)
            return cands, usage, False
        except Exception:
            return self._fallback(seeds, pkg, n, exclude), Usage(), True

    # ----- M1 ON: 안전 타입은 템플릿(phrase), 저위험 타입은 자유생성 -----
    async def _generate_seeded(
        self, ctx: StructuredContext, seeds: list[MissionCandidate], config: PipelineConfig
    ) -> tuple[list[MissionCandidate], Usage]:
        safe = [s for s in seeds if s.mission_type not in pool.FREE_ELIGIBLE_TYPES]
        free = [s for s in seeds if s.mission_type in pool.FREE_ELIGIBLE_TYPES]
        usage = Usage()
        out: list[MissionCandidate] = []
        if safe:
            cands, u = await self._generate_phrase(ctx, safe, config)
            out += cands
            usage = usage.add(u)
        if free:
            cands, u = await self._generate_free_typed(ctx, free, config)
            out += cands
            usage = usage.add(u)
        return out, usage

    async def _generate_free_typed(
        self, ctx: StructuredContext, free_seeds: list[MissionCandidate], config: PipelineConfig
    ) -> tuple[list[MissionCandidate], Usage]:
        """저위험 카테고리별로 미션 내용을 자유생성한다. mission_type은 요청 카테고리로 강제하고
        (LLM 오라벨→게이트 회피 방지), 부족분은 원래 템플릿 seed로 보충한다."""
        types = [s.mission_type for s in free_seeds]
        user = {"context": self._ctx_payload(ctx), "categories": types}
        if config.M5_structured:
            data, usage = await self.llm.structured(
                prompts.GEN_SYSTEM_FREE_TYPED, user, _FULL_SCHEMA, "missions"
            )
            generated = self._parse_full_structured(data)
        else:
            text, usage = await self.llm.text(
                prompts.GEN_SYSTEM_FREE_TYPED + _FREE_FORMAT_FULL, user
            )
            generated = self._parse_full_free(text, len(types))

        out: list[MissionCandidate] = []
        for i, seed in enumerate(free_seeds):
            if i < len(generated) and generated[i].title:
                # 카테고리 강제(요청 타입) — LLM이 다른 타입으로 라벨해도 무시
                out.append(generated[i].model_copy(update={"mission_type": types[i]}))
            else:
                out.append(seed)  # 자유생성 부족분 → 템플릿으로 보충
        return out, usage

    # ----- M1 OFF: 전체 생성 -----
    async def _generate_full(
        self, ctx: StructuredContext, config: PipelineConfig, n: int
    ) -> tuple[list[MissionCandidate], Usage]:
        user = {"context": self._ctx_payload(ctx), "n_missions": n}
        if config.M5_structured:
            data, usage = await self.llm.structured(
                prompts.GEN_SYSTEM_FULL, user, _FULL_SCHEMA, "missions"
            )
            return self._parse_full_structured(data), usage
        text, usage = await self.llm.text(prompts.GEN_SYSTEM_FULL + _FREE_FORMAT_FULL, user)
        return self._parse_full_free(text, n), usage

    # ----- M1 ON: 표현만 -----
    async def _generate_phrase(
        self, ctx: StructuredContext, seeds: list[MissionCandidate], config: PipelineConfig
    ) -> tuple[list[MissionCandidate], Usage]:
        user = {
            "context": self._ctx_payload(ctx),
            "missions": [
                {
                    "index": i,
                    "title": s.title,
                    "mission_type": s.mission_type,
                    "when": s.execution.when,
                }
                for i, s in enumerate(seeds)
            ],
        }
        if config.M5_structured:
            data, usage = await self.llm.structured(
                prompts.GEN_SYSTEM_PHRASE, user, _PHRASE_SCHEMA, "rationales"
            )
            return self._apply_phrase(seeds, data.get("items", [])), usage
        text, usage = await self.llm.text(prompts.GEN_SYSTEM_PHRASE + _FREE_FORMAT_PHRASE, user)
        return self._apply_phrase_free(seeds, text), usage

    # ----- 컨텍스트 직렬화 -----
    def _ctx_payload(self, ctx: StructuredContext) -> dict[str, Any]:
        return {
            "conditions": ctx.conditions,
            "medications": ctx.medications,
            "relations": [r.text for r in ctx.relations],  # 추론용(M3 OFF면 빈 리스트)
            "allowed_groundings": list(dict.fromkeys(r.cite for r in ctx.relations if r.cite)),
            "steps_avg": ctx.wearable.steps_avg,
            "trends": [  # 검진 지표 궤적 — 설명에서 이 사람의 상황을 언급하도록
                {"metric": t.label or t.code, "direction": t.direction, "adverse": t.adverse}
                for t in ctx.trends
            ],
            "clinical_facts": ctx.curated_facts,  # 외부 KG 정제 임상 요약 — 미션 근거로
            "success_rate": ctx.success_rate,
            "recent_missions": ctx.recent_mission_titles,  # 최근 배정분 — 반복 피하도록
        }

    # ----- 파싱: structured -----
    def _parse_full_structured(self, data: dict) -> list[MissionCandidate]:
        out = []
        for m in data.get("missions", []):
            title = (m.get("title") or "").strip()
            mt = _normalize_type(m.get("mission_type", ""), title)
            ex = m.get("execution") or {}
            out.append(
                MissionCandidate(
                    title=title,
                    rationale=(m.get("rationale") or "").strip(),
                    grounded_on=[g for g in (m.get("grounded_on") or []) if g],
                    execution=Execution(
                        when=(ex.get("when") or ""),
                        duration_min=ex.get("duration_min"),
                        time=policy.normalize_time(ex.get("time"), mt, ex.get("when") or ""),
                    ),
                    difficulty=max(1, int(m.get("difficulty") or 1)),
                    mission_type=mt,
                )
            )
        return [m for m in out if m.title]

    def _apply_phrase(
        self, seeds: list[MissionCandidate], items: list[dict]
    ) -> list[MissionCandidate]:
        by_index = {int(it.get("index", -1)): it for it in items}
        out = []
        for i, seed in enumerate(seeds):
            it = by_index.get(i, {})
            time = policy.normalize_time(it.get("time"), seed.mission_type, seed.execution.when)
            out.append(
                seed.model_copy(
                    update={
                        "rationale": (it.get("rationale") or "").strip(),
                        "grounded_on": [g for g in (it.get("grounded_on") or []) if g],
                        "execution": seed.execution.model_copy(update={"time": time}),
                    }
                )
            )
        return out

    # ----- 파싱: free text -----
    def _parse_full_free(self, text: str, n: int) -> list[MissionCandidate]:
        blocks = _split_blocks(text)
        out = []
        for block in blocks[:n]:
            title = _field(block, ("제목", "미션")) or block.strip().splitlines()[0]
            rationale = _field(block, ("이유", "근거", "설명")) or block.strip()
            title = title[:80].strip()
            out.append(
                MissionCandidate(
                    title=title,
                    rationale=rationale.strip(),
                    grounded_on=_ARROW.findall(block),
                    mission_type=_normalize_type("", title),
                )
            )
        return [m for m in out if m.title]

    def _apply_phrase_free(
        self, seeds: list[MissionCandidate], text: str
    ) -> list[MissionCandidate]:
        blocks = _split_blocks(text)
        out = []
        for i, seed in enumerate(seeds):
            block = blocks[i] if i < len(blocks) else ""
            out.append(
                seed.model_copy(
                    update={
                        "rationale": (_field(block, ("이유", "근거")) or block).strip(),
                        "grounded_on": _ARROW.findall(block),
                    }
                )
            )
        return out

    # ----- fallback (LLM 없음/실패) -----
    def _fallback(
        self,
        seeds: list[MissionCandidate] | None,
        pkg: PKG,
        n: int,
        exclude: set[str] | None = None,
    ) -> list[MissionCandidate]:
        if seeds:
            return seeds
        exclude = exclude or set()
        out: list[MissionCandidate] = []
        for t in pool.candidate_templates(pkg):
            if len(out) >= n:
                break
            if t["id"] in exclude:
                continue
            params = {k: v.get("base") for k, v in t.get("slots", {}).items()}
            title = t["template"].format(**params) if params else t["template"]
            out.append(MissionCandidate(title=title, mission_type=t["type"], template_id=t["id"]))
        return out


def _split_blocks(text: str) -> list[str]:
    t = text.strip()
    # '제목:' 마커가 있으면 그 단위로 분리(각 미션의 제목/이유/근거 라인이 한 덩어리로 묶임)
    if re.search(r"제목\s*[:：]", t):
        chunks = re.split(r"(?=제목\s*[:：])", t)
        return [c.strip() for c in chunks if re.search(r"제목\s*[:：]", c)]
    parts = re.split(r"\n\s*\n|\n(?=\d+[.)]\s)|\n(?=미션\s*\d)", t)
    return [p for p in (p.strip() for p in parts) if p]


def _field(block: str, keys: tuple[str, ...]) -> str | None:
    for line in block.splitlines():
        for key in keys:
            if key in line and ":" in line:
                return line.split(":", 1)[1].strip()
    return None


_EXECUTION_SCHEMA = {
    "type": "object",
    "properties": {
        "when": {"type": "string"},
        "duration_min": {"type": ["integer", "null"]},
        "time": {"type": "string"},
    },
    "required": ["when", "duration_min", "time"],
    "additionalProperties": False,
}

_FULL_SCHEMA = {
    "type": "object",
    "properties": {
        "missions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "rationale": {"type": "string"},
                    "grounded_on": {"type": "array", "items": {"type": "string"}},
                    "execution": _EXECUTION_SCHEMA,
                    "difficulty": {"type": "integer"},
                    "mission_type": {"type": "string", "enum": list(MISSION_TYPES)},
                },
                "required": [
                    "title",
                    "rationale",
                    "grounded_on",
                    "execution",
                    "difficulty",
                    "mission_type",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["missions"],
    "additionalProperties": False,
}

_PHRASE_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "rationale": {"type": "string"},
                    "grounded_on": {"type": "array", "items": {"type": "string"}},
                    "time": {"type": "string"},
                },
                "required": ["index", "rationale", "grounded_on", "time"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

_FREE_FORMAT_FULL = (
    " Output each mission as lines '제목: ...', '이유: ...', '근거: A->B; C->D', separated by a "
    "blank line."
)
_FREE_FORMAT_PHRASE = (
    " For each mission in order, output a block starting with '미션{index}', then lines "
    "'이유: ...' and '근거: A->B' (colon-separated)."
)
