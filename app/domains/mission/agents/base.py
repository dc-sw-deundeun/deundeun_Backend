"""LLM 호출 클라이언트 (GPT/OpenAI chat/completions).

LLM 텍스트 경로는 GPT(OpenAI)로 통일한다.
  base_url = https://api.openai.com/v1 , POST /chat/completions
  Authorization: Bearer {API Key}
- 모델·temperature 고정으로 ablation 변수 통제
- token usage 수집(비용 지표)
- structured(json) / free-text 모드 지원(M5 토글). strict json_schema 의존 없이
  **프롬프트-지시 JSON + 견고 파싱**으로 통일한다.
SDK 의존성 없이 httpx 직접 호출. 모든 에이전트가 하나의 LLMClient를 공유해 동일 모델·온도 보장.
"""

import asyncio
import json
from typing import Any

import httpx
from pydantic import BaseModel

from app.core.config import settings

_OPENAI_BASE = "https://api.openai.com/v1"
_RETRY_STATUS = {429, 500, 502, 503, 529}
_MAX_RETRIES = 5


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    calls: int = 0

    def add(self, other: "Usage") -> "Usage":
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            calls=self.calls + other.calls,
        )


class LLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = _OPENAI_BASE,
        model: str | None = None,
        temperature: float = 0.3,
        timeout_seconds: float | None = None,
        max_tokens: int = 2048,
        provider: str = "openai",
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.base_url = base_url.rstrip("/")
        self.model = model or settings.openai_model
        self.temperature = temperature
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.openai_timeout_seconds
        )
        self.max_tokens = max_tokens
        self.provider = provider

    @classmethod
    def for_provider(cls, temperature: float = 0.3) -> "LLMClient":
        """LLM 텍스트 경로는 GPT(OpenAI)로 통일한다. (모델은 settings.openai_model)"""
        return cls(
            api_key=settings.openai_api_key,
            base_url=_OPENAI_BASE,
            model=settings.openai_model,
            temperature=temperature,
            timeout_seconds=settings.openai_timeout_seconds,
            provider="openai",
        )

    @property
    def has_llm(self) -> bool:
        return bool(self.api_key)

    async def structured(
        self,
        system: str,
        user_obj: dict[str, Any],
        schema: dict[str, Any],
        schema_name: str,
    ) -> tuple[dict[str, Any], Usage]:
        instructed = (
            system
            + "\n\nRespond with ONLY a single valid JSON object that matches this JSON schema. "
            + "No markdown fences, no commentary.\nSchema:\n"
            + json.dumps(schema, ensure_ascii=False)
        )
        data = await self._call(self._payload(instructed, user_obj))
        return _extract_json(self._content(data)), self._usage(data)

    async def text(self, system: str, user_obj: dict[str, Any]) -> tuple[str, Usage]:
        data = await self._call(self._payload(system, user_obj))
        return self._content(data), self._usage(data)

    def _payload(self, system: str, user_obj: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_obj, ensure_ascii=False)},
            ],
        }

    async def _call(self, payload: dict[str, Any]) -> dict[str, Any]:
        """rate limit(429)·일시적 5xx는 지수 백오프로 재시도(Retry-After 존중)."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(url, headers=headers, json=payload)
                if response.status_code in _RETRY_STATUS and attempt < _MAX_RETRIES - 1:
                    wait = _retry_after_seconds(response.headers.get("Retry-After"), attempt)
                    await asyncio.sleep(min(wait, 30.0))
                    continue
                response.raise_for_status()
                return response.json()
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(float(2**attempt))
        if last_exc:
            raise last_exc
        raise RuntimeError("LLM call failed after retries")

    def _content(self, data: dict[str, Any]) -> str:
        choices = data.get("choices") or []
        if not choices:
            raise ValueError("LLM response has no choices.")
        content = (choices[0].get("message") or {}).get("content")
        if not content:
            raise ValueError("LLM response message has no content.")
        return content

    def _usage(self, data: dict[str, Any]) -> Usage:
        u = data.get("usage", {}) or {}
        prompt = u.get("prompt_tokens", u.get("input_tokens", 0)) or 0
        completion = u.get("completion_tokens", u.get("output_tokens", 0)) or 0
        total = u.get("total_tokens", prompt + completion) or 0
        return Usage(
            prompt_tokens=prompt, completion_tokens=completion, total_tokens=total, calls=1
        )


def _retry_after_seconds(retry_after: str | None, attempt: int) -> float:
    """Retry-After(초 단위 숫자)를 파싱하되, 숫자가 아니거나(HTTP-date 등) 없으면 지수 백오프로 폴백."""
    if retry_after:
        try:
            return float(retry_after)
        except ValueError:
            pass
    return float(2**attempt)


def _extract_json(text: str) -> dict[str, Any]:
    """모델이 코드펜스/잡설을 섞어도 첫 JSON 객체를 견고하게 추출한다."""
    s = text.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if "```" in s[3:] else s[3:]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip().rstrip("`").strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        start = s.find("{")
        end = s.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(s[start : end + 1])
        raise
