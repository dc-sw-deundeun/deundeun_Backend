from fastapi import APIRouter, Depends

from app.core.dependencies import get_current_user
from app.core.response import not_implemented_response
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get(
    "/today",
    summary="[프론트 작업 제외] 오늘의 미션 placeholder",
    description="미션 도메인은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def get_today_missions(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.post(
    "/{mission_id}/complete",
    summary="[프론트 작업 제외] 미션 완료 placeholder",
    description="미션 도메인은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def complete_mission(mission_id: int, current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.post(
    "/{mission_id}/verify",
    summary="[프론트 작업 제외] 미션 인증 placeholder",
    description="미션 도메인은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def verify_mission(mission_id: int, current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get(
    "/calendar",
    summary="[프론트 작업 제외] 미션 캘린더 placeholder",
    description="미션 도메인은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def get_mission_calendar(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get(
    "/statistics/weekly",
    summary="[프론트 작업 제외] 주간 미션 통계 placeholder",
    description="미션 도메인은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def get_weekly_statistics(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.post(
    "/notifications/send",
    summary="[프론트 작업 제외] 미션 알림 발송 placeholder",
    description="미션 알림 발송 API는 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def send_mission_notification(current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()
