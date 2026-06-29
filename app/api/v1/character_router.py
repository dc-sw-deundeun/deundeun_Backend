from fastapi import APIRouter

from app.core.response import not_implemented_response

router = APIRouter()


@router.get(
    "/me",
    summary="[프론트 작업 제외] 내 캐릭터 placeholder",
    description="캐릭터·성장 도메인은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def get_my_character():
    return not_implemented_response()


@router.post(
    "/me/experience",
    summary="[프론트 작업 제외] 캐릭터 경험치 추가 placeholder",
    description="캐릭터·성장 도메인은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def add_experience():
    return not_implemented_response()


@router.patch(
    "/me/stage",
    summary="[프론트 작업 제외] 캐릭터 단계 수정 placeholder",
    description="캐릭터·성장 도메인은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def update_stage():
    return not_implemented_response()
