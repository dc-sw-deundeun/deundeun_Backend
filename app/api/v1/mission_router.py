from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.response import not_implemented_response, success_response
from app.database.session import get_db
from app.domains.mission.service import MissionService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get(
    "/today",
    summary="[프론트 사용] 오늘의 미션 조회",
    description=(
        "인증된 사용자의 로컬 날짜 기준 오늘 배정된 미션 목록을 반환합니다. "
        "미션은 스케줄러가 매일 생성하며, 아직 생성 전이면 빈 목록을 반환합니다."
    ),
)
async def get_today_missions(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items = MissionService(db).get_today_missions(current_user.id)
    return success_response(data=[item.model_dump(mode="json") for item in items])


@router.post(
    "/{mission_id}/complete",
    summary="[프론트 사용] 미션 완료(self-report)",
    description=(
        "인증된 사용자가 본인 미션을 완료 처리합니다(self-report). 이미 완료된 미션은 멱등 처리합니다. "
        "본인 미션이 아니거나 없으면 404."
    ),
)
async def complete_mission(
    mission_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    MissionService(db).complete_mission(current_user.id, mission_id)
    return success_response(message="미션을 완료했습니다.")


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
