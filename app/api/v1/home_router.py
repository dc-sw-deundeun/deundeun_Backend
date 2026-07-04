from fastapi import APIRouter, Depends, Security

from app.core.dependencies import bearer_scheme, get_current_user, get_home_service
from app.core.response import success_response
from app.domains.home.service import HomeService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get(
    "",
    summary="[프론트 사용] 홈 화면 데이터 조회",
    description=(
        "홈 화면에서 필요한 사용자 정보, 캐릭터 성장 상태, 오늘의 미션, 읽지 않은 알림 수를 "
        "한 번에 조회합니다. 알림 수는 Phase 7 전까지 0으로 반환합니다."
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
                                "user": {
                                    "id": 1,
                                    "nickname": "든든이",
                                    "onboarding_step": "COMPLETED",
                                    "onboarding_completed": True,
                                },
                                "character": {
                                    "user_id": 1,
                                    "level": 1,
                                    "total_exp": 0,
                                    "current_level_exp": 0,
                                    "exp_to_next_level": 100,
                                    "progress_ratio": 0.0,
                                    "owned_animals": [
                                        {
                                            "animal_code": "frog",
                                            "name": "개구리",
                                            "unlocked_level": 1,
                                            "unlocked_at": "2026-07-02T12:00:00Z",
                                        }
                                    ],
                                    "updated_at": "2026-07-02T12:00:00Z",
                                },
                                "today_missions": {
                                    "date": "2026-07-02",
                                    "total": 1,
                                    "completed": 0,
                                    "items": [
                                        {
                                            "mission_id": 1,
                                            "template_code": "DEFAULT_SELF_CHECK",
                                            "title": "오늘의 건강 체크",
                                            "description": "오늘 하루 건강 상태를 스스로 확인해 보세요.",
                                            "category": "HEALTH",
                                            "verification_mode": "SELF_CHECK",
                                            "xp_reward": 10,
                                            "status": "ASSIGNED",
                                            "assigned_date": "2026-07-02",
                                            "source_record_id": 3,
                                        }
                                    ],
                                },
                                "unread_notification_count": 0,
                            },
                            "error_code": None,
                        }
                    }
                }
            }
        }
    },
)
def get_home(
    current_user: CurrentUser = Depends(get_current_user),
    service: HomeService = Depends(get_home_service),
):
    result = service.get_home(current_user.id)
    return success_response(data=result.model_dump(mode="json"))


@router.get(
    "/summary",
    summary="[프론트 사용] 홈 요약 조회",
    description=(
        "홈 상단/위젯에 필요한 최소 수치만 반환합니다. 캐릭터 상세와 오늘 미션 상세가 필요한 "
        "화면은 `GET /api/v1/home`을 사용하세요."
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
                                "nickname": "든든이",
                                "level": 1,
                                "total_exp": 0,
                                "progress_ratio": 0.0,
                                "owned_animal_count": 1,
                                "today_mission_total": 1,
                                "today_mission_completed": 0,
                                "unread_notification_count": 0,
                            },
                            "error_code": None,
                        }
                    }
                }
            }
        }
    },
)
def get_home_summary(
    current_user: CurrentUser = Depends(get_current_user),
    service: HomeService = Depends(get_home_service),
):
    result = service.get_summary(current_user.id)
    return success_response(data=result.model_dump(mode="json"))
