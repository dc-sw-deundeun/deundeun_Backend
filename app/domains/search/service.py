import json
import logging
from typing import Any

import httpx

from app.core.config import settings
from app.domains.search.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)

_neo4j_client: Neo4jClient | None = None


def _get_neo4j() -> Neo4jClient | None:
    global _neo4j_client
    if _neo4j_client is None:
        try:
            _neo4j_client = Neo4jClient()
        except Exception as exc:
            logger.warning("Neo4j connection unavailable: %s", exc)
    return _neo4j_client


class DiseaseSearchService:
    async def search(self, query: str) -> list[dict[str, Any]]:
        neo4j_data = self._get_neo4j_reference(query)
        return await self._generate_with_ai(query, neo4j_data)

    def _get_neo4j_reference(self, query: str) -> list[dict[str, Any]]:
        client = _get_neo4j()
        if client is None:
            return []
        return client.search_diseases(query, limit=5)

    async def _generate_with_ai(
        self, query: str, reference: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        if not settings.openai_api_key:
            return self._fallback(query, reference)

        ref_text = ""
        if reference:
            ref_text = "\n\n참고 데이터(Neo4j):\n" + json.dumps(reference, ensure_ascii=False)

        system_prompt = (
            "당신은 의학 정보 전문가입니다. 사용자가 입력한 질환/증상 키워드에 맞는 "
            "질환 정보를 한국어로 반환하세요. "
            "응답은 반드시 JSON 배열 형태여야 합니다: "
            '[{"name": "질환명(한국어)", "description": "간단한 설명(2-3문장)", '
            '"symptoms": ["증상1", "증상2", ...]}]. '
            "최대 5개 질환을 반환하세요. 결과가 없으면 빈 배열 []을 반환하세요."
        )
        user_prompt = f"검색어: {query}{ref_text}"

        try:
            payload = {
                "model": settings.openai_model,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "text": {"format": {"type": "json_object"}},
            }
            async with httpx.AsyncClient(timeout=settings.openai_timeout_seconds) as client:
                response = await client.post(
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": f"Bearer {settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                text = data["output"][0]["content"][0]["text"]
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return parsed
                for v in parsed.values():
                    if isinstance(v, list):
                        return v
                return []
        except Exception as exc:
            logger.warning("OpenAI disease search failed: %s", exc)
            return self._fallback(query, reference)

    def _fallback(self, query: str, reference: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not reference:
            return []
        return [
            {
                "name": r["name"],
                "description": f"{r['name']} 질환입니다.",
                "symptoms": r.get("symptoms", []),
            }
            for r in reference
        ]
