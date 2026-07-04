from pydantic import BaseModel


class ConnectedAppStatus(BaseModel):
    provider: str
    status: str  # CONNECTED / DISCONNECTED / ERROR


class ConnectedAppsResponse(BaseModel):
    apps: list[ConnectedAppStatus]


ConnectedAppToggleResponse = ConnectedAppStatus


class NotificationSettingsResponse(BaseModel):
    mission_alarm_enabled: bool
    record_alarm_enabled: bool
    email_alarm_enabled: bool
    push_alarm_enabled: bool


class NotificationSettingsUpdateRequest(BaseModel):
    mission_alarm_enabled: bool | None = None
    record_alarm_enabled: bool | None = None
    email_alarm_enabled: bool | None = None
    push_alarm_enabled: bool | None = None
