from fastapi import APIRouter, Depends, Security

from app.core.dependencies import bearer_scheme, get_character_service, get_current_user
from app.core.response import not_implemented_response, success_response
from app.domains.character.service import CharacterService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get(
    "/me",
    summary="[프론트 사용] 내 캐릭터 조회",
    description=(
        "인증된 사용자의 캐릭터 성장 상태와 실제 보유 동물 컬렉션을 조회합니다. "
        "프로필이 없으면 기본 상태와 frog 보유 row를 생성합니다. "
        "레벨업은 대표 동물 자동 변경이 아니라 owned_animals 누적 해금입니다. "
        "EXP/level 정책은 현재 mock 정책입니다. Authorization 헤더 필요."
    ),
    dependencies=[Security(bearer_scheme)],
)
def get_my_character(
    current_user: CurrentUser = Depends(get_current_user),
    service: CharacterService = Depends(get_character_service),
):
    result = service.get_my_character(current_user.id)
    return success_response(data=result.model_dump(mode="json"))


@router.get(
    "/animals",
    summary="[프론트 사용] 전체 동물 잠금/해금 상태 조회",
    description=(
        "전체 동물 카탈로그를 반환하고 현재 사용자의 보유 여부를 is_unlocked로 표시합니다. "
        "잠긴 동물도 unlock_level, required_total_exp와 함께 내려주므로 도감/진행도 UI에 사용할 수 있습니다. "
        "레벨업은 대표 동물 자동 변경이 아니라 사용자별 owned_animals 컬렉션 누적 해금입니다. "
        "Authorization 헤더 필요."
    ),
    dependencies=[Security(bearer_scheme)],
)
def list_animals(
    current_user: CurrentUser = Depends(get_current_user),
    service: CharacterService = Depends(get_character_service),
):
    animals = service.list_animals(current_user.id)
    return success_response(
        data={"animals": [animal.model_dump(mode="json") for animal in animals]}
    )


@router.post(
    "/me/experience",
    summary="[서버/내부] 캐릭터 경험치 추가 placeholder",
    description=(
        "프론트 공개 API가 아닙니다. 경험치 지급은 미션 완료 흐름에서 내부 서비스로 처리합니다. "
        "현재 직접 호출은 NOT_IMPLEMENTED(501)를 반환합니다."
    ),
)
async def add_experience():
    return not_implemented_response()


@router.patch(
    "/me/stage",
    summary="[서버/내부] 캐릭터 단계 수정 placeholder",
    description=(
        "프론트 공개 API가 아닙니다. stage/level은 EXP 정책으로 계산합니다. "
        "현재 직접 호출은 NOT_IMPLEMENTED(501)를 반환합니다."
    ),
)
async def update_stage():
    return not_implemented_response()
