import enum
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domains.onboarding.models import WearableProvider, WearableStatus


class WearableAction(str, enum.Enum):
    CONNECT = "CONNECT"
    SKIP = "SKIP"


class WearableConnectionItem(BaseModel):
    """연결된 웨어러블/헬스 플랫폼 상태."""

    model_config = ConfigDict(from_attributes=True)

    provider: WearableProvider
    status: WearableStatus
    scopes: list[str] | None = None
    last_synced_at: datetime | None = None


class ConsentPolicyItem(BaseModel):
    consent_type: str
    version: str
    required: bool


class OnboardingStatusResponse(BaseModel):
    onboarding_step: str
    is_completed: bool
    required_consents: list[ConsentPolicyItem]
    optional_consents: list[ConsentPolicyItem]
    wearable_connections: list[WearableConnectionItem]


class WearableConnectRequest(BaseModel):
    """웨어러블 연동 단계 처리.

    - CONNECT: 앱이 온디바이스에서 HealthKit/Health Connect 권한을 받은 뒤
      provider와 승인된 scope를 전달한다. 백엔드는 연결 상태만 저장한다.
    - SKIP: 권한을 건너뛰고 다음 단계로 진행한다.
    """

    action: WearableAction
    provider: WearableProvider | None = None
    scopes: list[str] | None = Field(default=None)

    @model_validator(mode="after")
    def _validate_connect(self) -> "WearableConnectRequest":
        if self.action == WearableAction.CONNECT and self.provider is None:
            raise ValueError("CONNECT 시 provider는 필수입니다.")
        return self


class WearableConnectResponse(BaseModel):
    onboarding_step: str
    connection: WearableConnectionItem | None = None


class WearableDisconnectResponse(BaseModel):
    onboarding_step: str
    wearable_connections: list[WearableConnectionItem]


class OnboardingCompleteResponse(BaseModel):
    onboarding_step: str
