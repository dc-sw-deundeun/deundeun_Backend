from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.response import not_implemented_response
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get(
    "/profile",
    summary="[프론트 작업 제외] 마이페이지 프로필 placeholder",
    description="마이페이지 도메인은 아직 구현되지 않았습니다. 현재 프로필 조회는 `GET /auth/me`를 사용하세요.",
)
async def get_profile(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.patch(
    "/password",
    summary="[프론트 작업 제외] 비밀번호 변경 placeholder",
    description="마이페이지 비밀번호 변경은 아직 구현되지 않았습니다. 비밀번호 재설정은 Auth API를 사용하세요.",
)
async def change_password(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get(
    "/app-lock",
    summary="[프론트 작업 제외] 앱 잠금 설정 조회 placeholder",
    description="앱 잠금 설정 API는 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def get_app_lock(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.patch(
    "/app-lock",
    summary="[프론트 작업 제외] 앱 잠금 설정 수정 placeholder",
    description="앱 잠금 설정 API는 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def update_app_lock(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.post(
    "/support",
    summary="[프론트 작업 제외] 문의 접수 placeholder",
    description="지원/문의 API는 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def submit_support(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.delete(
    "/account",
    summary="[프론트 작업 제외] 계정 삭제 placeholder",
    description="계정 삭제 API는 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def delete_account(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()
