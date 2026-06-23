from pydantic import BaseModel


class CurrentUser(BaseModel):
    """get_current_user 의존성이 반환하는 인증된 사용자 정보."""

    id: int


class UserProfileResponse(BaseModel):
    # user_id: int
    # nickname: str
    # profile_image_url: str | None
    pass


class UpdateProfileRequest(BaseModel):
    # nickname: str | None
    # profile_image_url: str | None
    pass
