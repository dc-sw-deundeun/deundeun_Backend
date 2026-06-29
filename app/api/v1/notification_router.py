from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.response import not_implemented_response
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get(
    "",
    summary="[프론트 작업 제외] 알림 목록 placeholder",
    description="알림 도메인은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def list_notifications(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.post(
    "/test",
    summary="[프론트 작업 제외] 테스트 알림 발송 placeholder",
    description="알림 도메인은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def send_test_notification(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get(
    "/settings",
    summary="[프론트 작업 제외] 알림 설정 조회 placeholder",
    description="알림 설정 API는 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def get_notification_settings(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.patch(
    "/settings",
    summary="[프론트 작업 제외] 알림 설정 수정 placeholder",
    description="알림 설정 API는 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def update_notification_settings(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()
