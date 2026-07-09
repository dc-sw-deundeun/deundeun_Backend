from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_user_service
from app.core.response import not_implemented_response, success_response
from app.database.session import get_db
from app.domains.my.schemas import (
    ConnectedAppsResponse,
    ConnectedAppStatus,
    ConnectedAppToggleResponse,
    NotificationSettingsResponse,
    NotificationSettingsUpdateRequest,
)
from app.domains.notification.models import NotificationPreference
from app.domains.onboarding.models import WearableProvider, WearableStatus
from app.domains.onboarding.repository import OnboardingRepository
from app.domains.user.schemas import CurrentUser, UpdateProfileRequest
from app.domains.user.service import UserService

router = APIRouter()

_NOTIFICATION_DEFAULTS = {
    "mission_alarm_enabled": True,
    "record_alarm_enabled": True,
    "email_alarm_enabled": True,
    "push_alarm_enabled": True,
}


@router.get(
    "/profile",
    summary="[프론트 사용] 마이페이지 프로필 조회",
    description="인증된 사용자의 마이페이지 프로필을 반환합니다. Authorization 헤더 필요.",
    openapi_extra={
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "message": "요청이 성공했습니다.",
                            "data": {
                                "id": 1,
                                "email": "demo-user@demo.deundeun.xyz",
                                "nickname": "든든데모",
                                "sex": "MALE",
                                "onboarding_step": "COMPLETED",
                                "timezone": "Asia/Seoul",
                                "status": "ACTIVE",
                                "created_at": "2026-07-01T13:00:00Z",
                            },
                            "error_code": None,
                        }
                    }
                }
            }
        }
    },
)
def get_profile(
    current_user: CurrentUser = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    profile = service.get_profile(current_user.id)
    return success_response(data=profile.model_dump(mode="json"))


@router.patch(
    "/profile",
    summary="[프론트 사용] 마이페이지 프로필 수정",
    description="현재 사용자의 닉네임을 수정합니다. 변경 후 수정된 프로필 전체를 반환합니다.",
    openapi_extra={
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": {
                            "success": True,
                            "message": "프로필을 수정했습니다.",
                            "data": {
                                "id": 1,
                                "email": "demo-user@demo.deundeun.xyz",
                                "nickname": "수정된닉네임",
                                "sex": "MALE",
                                "onboarding_step": "COMPLETED",
                                "timezone": "Asia/Seoul",
                                "status": "ACTIVE",
                                "created_at": "2026-07-01T13:00:00Z",
                            },
                            "error_code": None,
                        }
                    }
                }
            }
        }
    },
)
def update_profile(
    body: UpdateProfileRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    profile = service.update_profile(current_user.id, body)
    return success_response(message="프로필을 수정했습니다.", data=profile.model_dump(mode="json"))


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
    summary="[프론트 사용] 회원탈퇴",
    description=(
        "현재 계정을 소프트 탈퇴 처리합니다. 모든 refresh token을 폐기하고 token_version을 증가시켜 "
        "기존 access token도 이후 요청에서 무효화합니다. 유예 시간이 지난 DELETED 계정은 동일 이메일 "
        "재가입 시 물리 정리될 수 있습니다."
    ),
)
def delete_account(
    current_user: CurrentUser = Depends(get_current_user),
    service: UserService = Depends(get_user_service),
):
    service.delete_account(current_user.id)
    return success_response(message="회원탈퇴가 완료되었습니다.")


@router.get(
    "/connected-apps",
    response_model=ConnectedAppsResponse,
    summary="[프론트 사용] 연동 앱 목록 조회",
    description=(
        "현재 사용자의 헬스 앱 연동 상태를 반환합니다.\n\n"
        "- 지원 provider: `APPLE_HEALTH`, `SAMSUNG_HEALTH`, `GOOGLE_FIT`\n"
        "- 한 번도 설정하지 않은 앱은 `DISCONNECTED`로 반환됩니다.\n"
        "- status 값: `CONNECTED` / `DISCONNECTED`"
    ),
)
async def get_connected_apps(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = OnboardingRepository(db)
    connections = repo.list_wearable_connections(current_user.id)
    existing = {c.provider: c.status for c in connections}
    apps = [
        ConnectedAppStatus(
            provider=p.value, status=existing.get(p.value, WearableStatus.DISCONNECTED.value)
        )
        for p in WearableProvider
    ]
    return ConnectedAppsResponse(apps=apps)


@router.patch(
    "/connected-apps/{provider}",
    response_model=ConnectedAppToggleResponse,
    summary="[프론트 사용] 연동 앱 상태 토글",
    description=(
        "연동 앱 상태를 `CONNECTED ↔ DISCONNECTED`로 토글합니다.\n\n"
        "- `provider` 경로 파라미터: `APPLE_HEALTH` / `SAMSUNG_HEALTH` / `GOOGLE_FIT`\n"
        "- 현재 CONNECTED이면 DISCONNECTED, DISCONNECTED(또는 미설정)이면 CONNECTED로 전환합니다.\n"
        "- 지원하지 않는 provider 값은 400을 반환합니다."
    ),
)
async def toggle_connected_app(
    provider: str,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        provider_enum = WearableProvider(provider)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 provider: {provider}")
    repo = OnboardingRepository(db)
    existing = repo.find_wearable_connection(current_user.id, provider_enum.value)
    if existing and existing.status == WearableStatus.CONNECTED.value:
        new_status = WearableStatus.DISCONNECTED
    else:
        new_status = WearableStatus.CONNECTED
    conn = repo.upsert_wearable_connection(
        user_id=current_user.id,
        provider=provider_enum.value,
        status=new_status.value,
        scopes=None,
    )
    db.commit()
    db.refresh(conn)
    return ConnectedAppToggleResponse(provider=conn.provider, status=conn.status)


@router.get(
    "/notification-settings",
    response_model=NotificationSettingsResponse,
    summary="[프론트 사용] 알림 설정 조회",
    description=(
        "현재 사용자의 알림 설정을 반환합니다.\n\n"
        "알림 설정이 없는 경우 모든 항목을 `true`로 자동 초기화한 뒤 반환합니다.\n\n"
        "| 필드 | 화면 이름 |\n"
        "|------|-----------|\n"
        "| `mission_alarm_enabled` | 미션 리마인드 |\n"
        "| `record_alarm_enabled` | 기록 리마인드 |\n"
        "| `email_alarm_enabled` | 식단 기록 알림 |\n"
        "| `push_alarm_enabled` | 주간 리포트 |"
    ),
    openapi_extra={
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": {
                            "mission_alarm_enabled": True,
                            "record_alarm_enabled": True,
                            "email_alarm_enabled": True,
                            "push_alarm_enabled": True,
                        }
                    }
                }
            }
        }
    },
)
async def get_notification_settings(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    pref = db.query(NotificationPreference).filter_by(user_id=current_user.id).first()
    if pref is None:
        stmt = (
            pg_insert(NotificationPreference)
            .values(user_id=current_user.id, **_NOTIFICATION_DEFAULTS)
            .on_conflict_do_nothing(constraint="uq_notification_preferences_user")
            .returning(NotificationPreference)
        )
        result = db.execute(stmt)
        db.commit()
        pref = result.scalars().first()
        if pref is None:
            pref = db.query(NotificationPreference).filter_by(user_id=current_user.id).first()
    if pref is None:
        return NotificationSettingsResponse(**_NOTIFICATION_DEFAULTS)
    return NotificationSettingsResponse(
        mission_alarm_enabled=pref.mission_alarm_enabled,
        record_alarm_enabled=pref.record_alarm_enabled,
        email_alarm_enabled=pref.email_alarm_enabled,
        push_alarm_enabled=pref.push_alarm_enabled,
    )


@router.patch(
    "/notification-settings",
    response_model=NotificationSettingsResponse,
    summary="[프론트 사용] 알림 설정 업데이트",
    description=(
        "알림 설정을 부분 업데이트합니다. 변경할 항목만 포함해 전송하세요.\n\n"
        "모든 필드가 optional이며, null을 전송하면 해당 필드는 변경되지 않습니다.\n\n"
        "**예시** — 미션 리마인드만 끄기:\n"
        "```json\n"
        '{"mission_alarm_enabled": false}\n'
        "```"
    ),
    openapi_extra={
        "responses": {
            "200": {
                "content": {
                    "application/json": {
                        "example": {
                            "mission_alarm_enabled": False,
                            "record_alarm_enabled": True,
                            "email_alarm_enabled": True,
                            "push_alarm_enabled": True,
                        }
                    }
                }
            }
        }
    },
)
async def update_notification_settings(
    body: NotificationSettingsUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_data = body.model_dump(exclude_none=True)
    if not update_data:
        pref = db.query(NotificationPreference).filter_by(user_id=current_user.id).first()
        if pref is None:
            return NotificationSettingsResponse(**_NOTIFICATION_DEFAULTS)
        return NotificationSettingsResponse(
            mission_alarm_enabled=pref.mission_alarm_enabled,
            record_alarm_enabled=pref.record_alarm_enabled,
            email_alarm_enabled=pref.email_alarm_enabled,
            push_alarm_enabled=pref.push_alarm_enabled,
        )
    insert_values = {**_NOTIFICATION_DEFAULTS, **update_data, "user_id": current_user.id}
    stmt = (
        pg_insert(NotificationPreference)
        .values(**insert_values)
        .on_conflict_do_update(
            constraint="uq_notification_preferences_user",
            set_={**update_data, "updated_at": func.now()},
        )
        .returning(NotificationPreference)
    )
    result = db.execute(stmt)
    db.commit()
    pref = result.scalars().first()
    if pref is None:
        pref = db.query(NotificationPreference).filter_by(user_id=current_user.id).first()
    if pref is None:
        return NotificationSettingsResponse(**_NOTIFICATION_DEFAULTS)
    return NotificationSettingsResponse(
        mission_alarm_enabled=pref.mission_alarm_enabled,
        record_alarm_enabled=pref.record_alarm_enabled,
        email_alarm_enabled=pref.email_alarm_enabled,
        push_alarm_enabled=pref.push_alarm_enabled,
    )
