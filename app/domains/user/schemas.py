from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    # user_id: int
    # nickname: str
    # profile_image_url: str | None
    pass


class UpdateProfileRequest(BaseModel):
    # nickname: str | None
    # profile_image_url: str | None
    pass
