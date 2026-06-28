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

from app.domains.mission import pool, prompts
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

# LLM(특히 HCX)이 enum 대신 한국어/변형 타입을 줄 때 매핑
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
        self.llm = llm or LLMClient()

    async def generate(
        self,
        ctx: StructuredContext,
        pkg_client: PKGClient,
        pkg: PKG,
        config: PipelineConfig,
        n: int,
    ) -> tuple[list[MissionCandidate], Usage]:
        seeds = build_seeds(pkg_client, pkg, n) if config.M1_template else None

        if not self.llm.has_llm:
            return self._fallback(seeds, pkg, n), Usage()

        try:
            if config.M1_template:
                return await self._generate_phrase(ctx, seeds or [], config)
            return await self._generate_full(ctx, config, n)
        except Exception:
            return self._fallback(seeds, pkg, n), Usage()

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
            "missions": [{"index": i, "title": s.title} for i, s in enumerate(seeds)],
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
            "success_rate": ctx.success_rate,
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
                        when=(ex.get("when") or ""), duration_min=ex.get("duration_min")
                    ),
                    difficulty=int(m.get("difficulty") or 1),
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
            out.append(
                seed.model_copy(
                    update={
                        "rationale": (it.get("rationale") or "").strip(),
                        "grounded_on": [g for g in (it.get("grounded_on") or []) if g],
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
        self, seeds: list[MissionCandidate] | None, pkg: PKG, n: int
    ) -> list[MissionCandidate]:
        if seeds:
            return seeds
        out = []
        for t in pool.candidate_templates(pkg)[:n]:
            params = {k: v.get("base") for k, v in t.get("slots", {}).items()}
            title = t["template"].format(**params) if params else t["template"]
            out.append(
                MissionCandidate(title=title, mission_type=t["type"], template_id=t["id"])
            )
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
    },
    "required": ["when", "duration_min"],
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
                },
                "required": ["index", "rationale", "grounded_on"],
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
    " For each mission in order output '미션{index}: 이유 - ... / 근거 - A->B' on its own block."
)
