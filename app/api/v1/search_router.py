from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user
from app.domains.search.schemas import DiseaseResult, DiseaseSearchResponse
from app.domains.search.service import DiseaseSearchService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


def get_disease_search_service() -> DiseaseSearchService:
    return DiseaseSearchService()


@router.get(
    "/diseases",
    response_model=DiseaseSearchResponse,
    summary="[프론트 사용] 질환 검색 (의학 KG + AI)",
    description=(
        "한국어 키워드로 질환 정보를 검색합니다.\n\n"
        "내부 동작:\n"
        "1. 의학 지식 그래프(Neo4j)에서 연관 질환 참조 데이터를 조회합니다.\n"
        "2. AI(OpenAI)가 참조 데이터를 기반으로 한국어 설명을 생성합니다.\n"
        "3. Neo4j 미연결 시에도 AI 단독으로 결과를 반환합니다.\n\n"
        "**응답 필드:**\n"
        "- `results[].name`: 질환명 (한국어)\n"
        "- `results[].description`: 질환 설명 (2~3문장)\n"
        "- `results[].symptoms`: 주요 증상 목록\n\n"
        "검색 결과가 없으면 `results: []`를 반환합니다."
    ),
)
async def search_diseases(
    q: str = Query(..., min_length=1, description="검색 키워드 (한국어/영문)"),
    current_user: CurrentUser = Depends(get_current_user),
    service: DiseaseSearchService = Depends(get_disease_search_service),
):
    results = await service.search(q)
    return DiseaseSearchResponse(results=[DiseaseResult.model_validate(r) for r in results])
