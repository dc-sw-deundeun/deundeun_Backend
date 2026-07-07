from fastapi import APIRouter, Depends, Query, Security

from app.core.dependencies import (
    bearer_scheme,
    get_current_user,
    get_notification_service,
)
from app.core.response import success_response
from app.domains.notification.service import NotificationService
from app.domains.user.schemas import CurrentUser

router = APIRouter()


@router.get(
    "",
    summary="[프론트 사용] 알림 목록 조회",
    description=(
        "인증된 사용자의 알림함 목록을 최신순으로 반환합니다. "
        "알림 설정은 `/api/v1/my/notification-settings`를 사용하세요."
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
                                "items": [
                                    {
                                        "id": 1,
                                        "type": "ANALYSIS_COMPLETED",
                                        "title": "건강 분석이 완료됐어요",
                                        "body": "건강 지표 분석 결과를 확인해 보세요.",
                                        "deep_link": "deundeun://health-metrics/analyses/12",
                                        "read_at": None,
                                        "created_at": "2026-07-06T12:00:00Z",
                                    }
                                ],
                                "total": 1,
                                "unread_count": 1,
                                "limit": 20,
                                "offset": 0,
                            },
                            "error_code": None,
                        }
                    }
                }
            }
        }
    },
)
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    unread_only: bool = Query(default=False),
    current_user: CurrentUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    result = service.list_notifications(
        current_user.id,
        limit=limit,
        offset=offset,
        unread_only=unread_only,
    )
    return success_response(data=result.model_dump(mode="json"))


@router.patch(
    "/{notification_id}/read",
    summary="[프론트 사용] 알림 읽음 처리",
    description="인증된 사용자의 알림을 읽음 처리합니다. 이미 읽은 알림은 멱등하게 동일 결과를 반환합니다.",
    dependencies=[Security(bearer_scheme)],
)
def mark_notification_read(
    notification_id: int,
    current_user: CurrentUser = Depends(get_current_user),
    service: NotificationService = Depends(get_notification_service),
):
    result = service.mark_as_read(current_user.id, notification_id)
    return success_response(data=result.model_dump(mode="json"))
