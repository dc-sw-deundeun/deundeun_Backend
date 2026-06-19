from pydantic import BaseModel


class OnboardingStatusResponse(BaseModel):
    # initial_checkup_completed: bool
    # wearable_connected: bool
    # completed_at: str | None
    pass


class InitialCheckupRequest(BaseModel):
    pass


class WearableConnectRequest(BaseModel):
    # device_type: str
    # device_token: str
    pass
