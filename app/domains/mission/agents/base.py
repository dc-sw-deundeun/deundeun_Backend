import json
from typing import Any

import httpx

from app.core.config import settings


class StructuredLLMAgent:
    """OpenAI 구조화 출력(structured json_schema)을 호출하는 에이전트 베이스.

    health_metric.explanation_service.HealthMetricExplanationService와 동일한
    호출 패턴(OpenAI /v1/responses, strict json_schema, store=False)을 따른다.
    SDK 의존성 없이 httpx로 직접 호출하며, 호출/파싱만 담당한다.
    fallback과 결과 매핑은 각 에이전트가 책임진다.
    """

    schema_name: str = "agent_output"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.model = model or settings.openai_model
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.openai_timeout_seconds
        )

    @property
    def has_llm(self) -> bool:
        """API 키가 있어 LLM 호출이 가능한지."""
        return bool(self.api_key)

    def system_prompt(self) -> str:
        raise NotImplementedError

    def response_schema(self) -> dict[str, Any]:
        raise NotImplementedError

    async def generate(self, user_input: dict[str, Any]) -> dict[str, Any]:
        """user_input(JSON 직렬화 가능 dict)을 보내고 파싱된 dict를 반환한다."""
        payload = self._build_payload(user_input)
        data = await self._call_openai(payload)
        return self._parse_response(data)

    async def _call_openai(self, payload: dict[str, Any]) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            return response.json()

    def _build_payload(self, user_input: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self.model,
            "input": [
                {"role": "system", "content": self.system_prompt()},
                {"role": "user", "content": json.dumps(user_input, ensure_ascii=False)},
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": self.schema_name,
                    "strict": True,
                    "schema": self.response_schema(),
                }
            },
            "store": False,
        }

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        text = data.get("output_text") or self._extract_output_text(data)
        if not text:
            raise ValueError("OpenAI response did not include output text.")
        return json.loads(text)

    def _extract_output_text(self, data: dict[str, Any]) -> str | None:
        for output in data.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"]
        return None
