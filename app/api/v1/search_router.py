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
    summary="질환 검색 (의학 KG + AI)",
)
async def search_diseases(
    q: str = Query(..., min_length=1, description="검색 키워드 (한국어/영문)"),
    current_user: CurrentUser = Depends(get_current_user),
    service: DiseaseSearchService = Depends(get_disease_search_service),
):
    results = await service.search(q)
    return DiseaseSearchResponse(
        results=[DiseaseResult.model_validate(r) for r in results]
    )
