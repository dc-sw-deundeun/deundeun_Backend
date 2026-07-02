from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.response import success_response
from app.domains.pkg.dependencies import get_pkg_service
from app.domains.pkg.service import PkgService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get(
    "/{user_id}",
    summary="[내부/서비스] 개인 지식그래프(PKG) 조회",
    description=(
        "user의 최신 검증 검진에서 조건·플래그를 도출하고 큐레이션 시드로 합병증 엣지를 조립해 "
        "미션 생성 엔진(#17)이 소비하는 PKG 객체를 반환합니다(스냅샷은 Postgres에 영속). "
        "검증된 검진이 없으면 404."
    ),
)
def get_pkg(
    user_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: PkgService = Depends(get_pkg_service),
):
    pkg = service.build_pkg(user_id)
    return success_response(data=pkg.model_dump(mode="json"))
