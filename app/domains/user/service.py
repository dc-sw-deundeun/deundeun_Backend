from datetime import UTC, datetime

from app.core.exceptions import BadRequestException
from app.domains.auth.exceptions import InvalidTokenException
from app.domains.user.models import UserStatus
from app.domains.user.repository import UserRepository
from app.domains.user.schemas import MeResponse, UpdateProfileRequest


class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def get_profile(self, user_id: int) -> MeResponse:
        user = self.repo.find_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidTokenException()
        return MeResponse.model_validate(user)

    def update_profile(self, user_id: int, request: UpdateProfileRequest) -> MeResponse:
        user = self.repo.find_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidTokenException()

        if request.nickname is None:
            raise BadRequestException(
                message="변경할 프로필 값을 입력해 주세요.",
                error_code="PROFILE_UPDATE_EMPTY",
            )

        user.nickname = request.nickname
        self.repo.commit()
        return MeResponse.model_validate(user)

    def change_password(self, user_id: int, current_password: str, new_password: str) -> None:
        raise NotImplementedError

    def delete_account(self, user_id: int) -> None:
        user = self.repo.find_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidTokenException()

        user.status = UserStatus.DELETED
        user.token_version += 1
        self.repo.revoke_all_refresh_tokens(user_id, datetime.now(UTC))
        self.repo.commit()
