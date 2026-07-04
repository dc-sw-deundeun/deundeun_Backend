from fastapi import APIRouter, Depends, Security

from app.core.dependencies import bearer_scheme, get_current_user, get_mission_service
from app.core.response import not_implemented_response, success_response
from app.domains.mission.service import MissionService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get(
    "/today",
    summary="[프론트 사용] 오늘의 미션 조회",
    description=(
        "인증된 사용자의 timezone 기준 오늘 배정된 미션 목록과 완료 집계를 반환합니다. "
        "미션은 스케줄러가 매일 PKG 기반으로 생성하며, 아직 생성 전이면 빈 목록을 반환합니다."
    ),
    dependencies=[Security(bearer_scheme)],
    openapi_extra={
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "message": "요청이 성공했습니다.",
                            "data": {
                                "date": "2026-07-04",
                                "total": 1,
                                "completed": 0,
                                "items": [
                                    {
                                        "mission_id": 1,
                                        "template_code": "walk_after_meal",
                                        "title": "식후 15분 걷기",
                                        "status": "ASSIGNED",
                                        "assigned_date": "2026-07-04",
                                        "xp_reward": 0,
                                        "completed_at": None,
                                        "source_record_id": None,
                                        "rationale": "고혈압 관리를 위해 식후 가벼운 운동이 도움이 됩니다.",
                                        "mission_type": "exercise",
                                        "difficulty": 2,
                                        "execution": {"when": "식후", "duration_min": 15},
                                        "grounded_on": ["고혈압->심혈관질환"],
                                        "source": "generated",
                                        "description": None,
                                        "category": None,
                                        "verification_mode": None,
                                    }
                                ],
                            },
                            "error_code": None,
                        }
                    }
                }
            }
        }
    },
)
def get_today_missions(
    current_user: CurrentUser = Depends(get_current_user),
    service: MissionService = Depends(get_mission_service),
):
    result = service.get_today_missions(current_user.id)
    return success_response(data=result.model_dump(mode="json"))


@router.post(
    "/{mission_id}/complete",
    summary="[프론트 사용] 미션 완료(self-report)",
    description=(
        "인증된 사용자가 본인 미션을 완료 처리합니다(self-report). 이미 완료된 미션은 멱등 처리합니다. "
        "본인 미션이 아니거나 없으면 404."
    ),
)
def complete_mission(
    mission_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: MissionService = Depends(get_mission_service),
):
    service.complete_mission(current_user.id, mission_id)
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
