from datetime import date

from fastapi import APIRouter, Depends, Query, Security

from app.core.dependencies import bearer_scheme, get_current_user, get_mission_service
from app.core.response import not_implemented_response, success_response
from app.domains.mission.service import MissionService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


def _ok_example(data: object) -> dict:
    """Swagger 200 응답 예시(success_response 봉투 형태)."""
    return {
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "message": "요청이 성공했습니다.",
                            "data": data,
                            "error_code": None,
                        }
                    }
                }
            }
        }
    }


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
                                        "xp_reward": 20,
                                        "completed_at": None,
                                        "source_record_id": None,
                                        "rationale": "고혈압 관리를 위해 식후 가벼운 운동이 도움이 됩니다.",
                                        "mission_type": "exercise",
                                        "difficulty": 2,
                                        "execution": {
                                            "when": "식후",
                                            "duration_min": 15,
                                            "time": "13:00",
                                        },
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
        "인증된 사용자가 본인 미션을 완료 처리합니다(self-report). 완료 즉시 xp_reward만큼 캐릭터 EXP가 지급되며, "
        "레벨업 시 알림이 생성됩니다. 이미 완료된 미션은 no-op으로 멱등 처리합니다. "
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


@router.delete(
    "/{mission_id}/complete",
    summary="[프론트 사용] 미션 완료(인증) 취소",
    description=(
        "인증된 사용자가 본인 미션의 완료 처리를 취소합니다(오탭 등으로 잘못 완료했을 때). "
        "이미 미완료(ASSIGNED) 상태면 멱등 처리합니다. 본인 미션이 아니거나 없으면 404."
    ),
)
def cancel_mission_completion(
    mission_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: MissionService = Depends(get_mission_service),
):
    service.cancel_mission_completion(current_user.id, mission_id)
    return success_response(message="미션 완료를 취소했습니다.")


@router.post(
    "/{mission_id}/verify",
    summary="[프론트 작업 제외] 미션 인증 placeholder",
    description="미션 도메인은 아직 구현되지 않았습니다. 호출 시 NOT_IMPLEMENTED(501)를 반환합니다.",
)
async def verify_mission(mission_id: int, current_user: CurrentUser = Depends(get_current_user)):
    return not_implemented_response()


@router.get(
    "/date/{target_date}",
    summary="[프론트 사용] 날짜별 미션 조회",
    description="특정 날짜(YYYY-MM-DD)에 배정된 미션 목록과 완료 집계를 반환합니다(/today와 동일 shape).",
    dependencies=[Security(bearer_scheme)],
    openapi_extra=_ok_example(
        {
            "date": "2026-07-06",
            "total": 1,
            "completed": 0,
            "items": [
                {
                    "mission_id": 10,
                    "title": "식후 15분 걷기",
                    "status": "ASSIGNED",
                    "assigned_date": "2026-07-06",
                    "xp_reward": 20,
                    "mission_type": "exercise",
                    "difficulty": 2,
                    "execution": {"when": "식후", "duration_min": 15, "time": "13:00"},
                    "source": "generated",
                }
            ],
        }
    ),
)
def get_missions_by_date(
    target_date: date,
    current_user: CurrentUser = Depends(get_current_user),
    service: MissionService = Depends(get_mission_service),
):
    result = service.get_missions_for_date(current_user.id, target_date)
    return success_response(data=result.model_dump(mode="json"))


@router.get(
    "/calendar",
    summary="[프론트 사용] 월간 미션 캘린더",
    description="해당 연·월에 미션이 있는 날의 일별 집계(total/completed)를 반환합니다.",
    dependencies=[Security(bearer_scheme)],
    openapi_extra=_ok_example(
        {
            "year": 2026,
            "month": 7,
            "days": [
                {"date": "2026-07-06", "total": 3, "completed": 2},
                {"date": "2026-07-15", "total": 2, "completed": 0},
            ],
        }
    ),
)
def get_mission_calendar(
    year: int = Query(ge=2000, le=2100),
    month: int = Query(ge=1, le=12),
    current_user: CurrentUser = Depends(get_current_user),
    service: MissionService = Depends(get_mission_service),
):
    result = service.get_monthly_calendar(current_user.id, year, month)
    return success_response(data=result.model_dump(mode="json"))


@router.get(
    "/statistics/weekly",
    summary="[프론트 사용] 주간 미션 통계",
    description="date(없으면 오늘)가 속한 주(월~일)의 일별·합계 집계를 반환합니다.",
    dependencies=[Security(bearer_scheme)],
    openapi_extra=_ok_example(
        {
            "week_start": "2026-07-06",
            "week_end": "2026-07-12",
            "total": 5,
            "completed": 3,
            "days": [
                {"date": "2026-07-06", "total": 2, "completed": 1},
                {"date": "2026-07-07", "total": 0, "completed": 0},
            ],
        }
    ),
)
def get_weekly_statistics(
    ref_date: date | None = Query(default=None, alias="date"),
    current_user: CurrentUser = Depends(get_current_user),
    service: MissionService = Depends(get_mission_service),
):
    result = service.get_weekly_statistics(current_user.id, ref_date=ref_date)
    return success_response(data=result.model_dump(mode="json"))


@router.get(
    "/statistics/summary",
    summary="[프론트 사용] 미션 총 완료 통계",
    description="전체 기간 총 배정·완료 수와 완성도(completion_rate)를 반환합니다.",
    dependencies=[Security(bearer_scheme)],
    openapi_extra=_ok_example(
        {"total_assigned": 120, "total_completed": 88, "completion_rate": 0.733}
    ),
)
def get_statistics_summary(
    current_user: CurrentUser = Depends(get_current_user),
    service: MissionService = Depends(get_mission_service),
):
    result = service.get_statistics_summary(current_user.id)
    return success_response(data=result.model_dump(mode="json"))
