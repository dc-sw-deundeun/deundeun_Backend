from fastapi import APIRouter

from app.core.response import not_implemented_response

router = APIRouter()


@router.get(
    "",
    summary="[프론트 작업 제외] 홈 화면 데이터 placeholder",
    description="홈 집계 API는 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def get_home():
    return not_implemented_response()


@router.get(
    "/summary",
    summary="[프론트 작업 제외] 홈 요약 placeholder",
    description="홈 집계 API는 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def get_home_summary():
    return not_implemented_response()
