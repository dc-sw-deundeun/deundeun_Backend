from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CharacterOwnedAnimalResponse(BaseModel):
    animal_code: str
    name: str
    unlocked_level: int
    image_urls: list[str]
    unlocked_at: datetime | None = None


class CharacterCatalogAnimalResponse(BaseModel):
    animal_code: str
    name: str
    unlock_level: int
    required_total_exp: int
    image_urls: list[str]
    is_unlocked: bool
    unlocked_at: datetime | None = None


class CharacterProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: int
    level: int
    total_exp: int
    current_level_exp: int
    exp_to_next_level: int
    progress_ratio: float = Field(ge=0.0, le=1.0)
    owned_animals: list[CharacterOwnedAnimalResponse]
    updated_at: datetime | None = None


class CharacterGainExpResponse(BaseModel):
    profile: CharacterProfileResponse
    exp_gained: int
    level_before: int
    level_after: int
    leveled_up: bool
