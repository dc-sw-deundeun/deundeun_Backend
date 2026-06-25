import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.domains.health_metric.schemas import (
    HealthMetricEvaluationItem,
    HealthMetricEvaluationRequest,
    HealthMetricExplanation,
    HealthMetricItemExplanation,
)

logger = logging.getLogger(__name__)

DISCLAIMER = "이 설명은 건강검진 결과를 쉽게 이해하기 위한 참고 정보이며, 진단이나 치료 지시가 아닙니다."


class HealthMetricExplanationService:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.model = model or settings.openai_model
        self.timeout_seconds = (
            timeout_seconds
            if timeout_seconds is not None
            else settings.openai_timeout_seconds
        )

    async def build_explanation(
        self,
        request: HealthMetricEvaluationRequest,
        results: list[HealthMetricEvaluationItem],
    ) -> HealthMetricExplanation:
        if not self.api_key:
            return self._fallback(results)

        try:
            payload = self._build_openai_payload(request, results)
            data = await self._call_openai(payload)
            explanation = self._parse_openai_response(data)
            return HealthMetricExplanation(**explanation, status="generated")
        except Exception as exc:
            logger.warning("OpenAI health metric explanation failed: %s", exc)
            return self._fallback(results)

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

    def _build_openai_payload(
        self,
        request: HealthMetricEvaluationRequest,
        results: list[HealthMetricEvaluationItem],
    ) -> dict[str, Any]:
        input_data = {
            "sex": request.sex,
            "results": [item.model_dump(mode="json") for item in results],
        }
        return {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": (
                        "You explain health checkup metric evaluation results in Korean. "
                        "Use language that non-medical readers of any age can understand. "
                        "Do not change or contradict the provided normal/caution/risk/unknown statuses. "
                        "Do not diagnose disease. Do not recommend starting, stopping, or changing medication. "
                        "Do not give treatment instructions. Explain only what the provided checkup result may mean "
                        "and when it is reasonable to consult a clinician."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(input_data, ensure_ascii=False),
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "health_metric_explanation",
                    "strict": True,
                    "schema": self._response_schema(),
                }
            },
            "store": False,
        }

    def _parse_openai_response(self, data: dict[str, Any]) -> dict[str, Any]:
        text = data.get("output_text")
        if not text:
            text = self._extract_output_text(data)
        if not text:
            raise ValueError("OpenAI response did not include output text.")

        parsed = json.loads(text)
        parsed["disclaimer"] = parsed.get("disclaimer") or DISCLAIMER
        return parsed

    def _extract_output_text(self, data: dict[str, Any]) -> str | None:
        for output in data.get("output", []):
            for content in output.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return content["text"]
        return None

    def _fallback(
        self, results: list[HealthMetricEvaluationItem]
    ) -> HealthMetricExplanation:
        risk_items = [item for item in results if item.status == "risk"]
        caution_items = [item for item in results if item.status == "caution"]
        unknown_items = [item for item in results if item.status == "unknown"]

        if risk_items:
            summary = "위험으로 분류된 항목이 있어 결과를 확인하고 필요하면 전문가와 상담하는 것이 좋습니다."
        elif caution_items:
            summary = "주의로 분류된 항목이 있어 생활습관과 추적 확인이 도움이 될 수 있습니다."
        elif unknown_items and len(unknown_items) == len(results):
            summary = "판정할 수 없는 항목만 포함되어 있어 기준에 맞는 항목명과 수치를 다시 확인해야 합니다."
        else:
            summary = "제공된 기준으로는 대부분 정상 범위에 해당합니다."

        highlights = [
            self._highlight(item)
            for item in [*risk_items, *caution_items, *unknown_items][:5]
        ]
        if not highlights:
            highlights = ["현재 입력된 항목에는 주의나 위험으로 분류된 값이 없습니다."]

        return HealthMetricExplanation(
            status="fallback",
            summary=summary,
            highlights=highlights,
            item_explanations=[
                HealthMetricItemExplanation(
                    canonical_test_code=item.canonical_test_code,
                    input_label=item.input_label,
                    title=item.name or item.input_label,
                    explanation=self._item_explanation(item),
                    status_label=item.status_label,
                )
                for item in results
            ],
            disclaimer=DISCLAIMER,
        )

    def _highlight(self, item: HealthMetricEvaluationItem) -> str:
        name = item.name or item.input_label
        detail = f" ({item.note})" if item.note else ""
        return f"{name} 항목은 {self._status_phrase(item)} 분류되었습니다{detail}."

    def _item_explanation(self, item: HealthMetricEvaluationItem) -> str:
        name = item.name or item.input_label
        value = f"{item.value:g}{item.unit or ''}"
        note = f" {item.note}에 해당합니다." if item.note else ""
        if item.status == "normal":
            return f"{name} 수치가 {value}로, 제공된 기준에서 정상 범위로 분류됩니다."
        if item.status == "caution":
            return f"{name} 수치가 {value}로, 제공된 기준에서 주의 범위로 분류됩니다.{note}"
        if item.status == "risk":
            return f"{name} 수치가 {value}로, 제공된 기준에서 위험 범위로 분류됩니다.{note} 진단은 아니므로 필요하면 전문가와 상담하세요."
        return f"{name} 항목은 현재 서버 기준표로 판정할 수 없습니다. 항목명이나 기준 지원 여부를 확인하세요."

    def _status_phrase(self, item: HealthMetricEvaluationItem) -> str:
        if item.status == "normal":
            return "정상으로"
        if item.status == "caution":
            return "주의로"
        if item.status == "risk":
            return "위험으로"
        return "판정불가로"

    def _response_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string",
                    "description": "A short Korean summary of the user's current checkup situation.",
                },
                "highlights": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Important Korean bullet points, prioritizing risk and caution items.",
                },
                "item_explanations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "canonical_test_code": {"type": ["string", "null"]},
                            "input_label": {"type": "string"},
                            "title": {"type": "string"},
                            "explanation": {"type": "string"},
                            "status_label": {"type": "string"},
                        },
                        "required": [
                            "canonical_test_code",
                            "input_label",
                            "title",
                            "explanation",
                            "status_label",
                        ],
                        "additionalProperties": False,
                    },
                },
                "disclaimer": {"type": "string"},
            },
            "required": ["summary", "highlights", "item_explanations", "disclaimer"],
            "additionalProperties": False,
        }
