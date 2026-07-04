from pydantic import BaseModel

from app.domains.character.schemas import CharacterProfileResponse
from app.domains.mission.schemas import TodayMissionsResponse


class HomeUserBlock(BaseModel):
    id: int
    nickname: str
    onboarding_step: str
    onboarding_completed: bool


class HomeResponse(BaseModel):
    user: HomeUserBlock
    character: CharacterProfileResponse
    today_missions: TodayMissionsResponse
    unread_notification_count: int = 0


class HomeSummaryResponse(BaseModel):
    nickname: str
    level: int
    total_exp: int
    progress_ratio: float
    owned_animal_count: int
    today_mission_total: int
    today_mission_completed: int
    unread_notification_count: int = 0
