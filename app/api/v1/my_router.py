from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.response import not_implemented_response
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
from app.domains.user.schemas import CurrentUser

router = APIRouter()

_NOTIFICATION_DEFAULTS = {
    "mission_alarm_enabled": True,
    "record_alarm_enabled": True,
    "email_alarm_enabled": True,
    "push_alarm_enabled": True,
}


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


@router.get(
    "/connected-apps",
    response_model=ConnectedAppsResponse,
    summary="연동 앱 목록 조회",
)
async def get_connected_apps(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = OnboardingRepository(db)
    connections = repo.list_wearable_connections(current_user.id)
    existing = {c.provider: c.status for c in connections}
    apps = [
        ConnectedAppStatus(provider=p.value, status=existing.get(p.value, WearableStatus.DISCONNECTED.value))
        for p in WearableProvider
    ]
    return ConnectedAppsResponse(apps=apps)


@router.patch(
    "/connected-apps/{provider}",
    response_model=ConnectedAppToggleResponse,
    summary="연동 앱 상태 토글",
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
    return ConnectedAppToggleResponse(provider=conn.provider, status=conn.status)


@router.get(
    "/notification-settings",
    response_model=NotificationSettingsResponse,
    summary="알림 설정 조회",
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
    summary="알림 설정 업데이트",
)
async def update_notification_settings(
    body: NotificationSettingsUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    update_data = body.model_dump(exclude_none=True) or _NOTIFICATION_DEFAULTS
    insert_values = {**_NOTIFICATION_DEFAULTS, **update_data, "user_id": current_user.id}
    stmt = (
        pg_insert(NotificationPreference)
        .values(**insert_values)
        .on_conflict_do_update(
            constraint="uq_notification_preferences_user",
            set_=update_data,
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
