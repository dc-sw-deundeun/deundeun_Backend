import logging

from app.core.exceptions import BadRequestException
from app.domains.auth.exceptions import InvalidTokenException
from app.domains.character import policy
from app.domains.character.models import CharacterGrowthLog, CharacterOwnedAnimal, CharacterProfile
from app.domains.character.repository import CharacterRepository
from app.domains.character.schemas import (
    CharacterCatalogAnimalResponse,
    CharacterGainExpResponse,
    CharacterOwnedAnimalResponse,
    CharacterProfileResponse,
)
from app.domains.mission.policy import calculate_exp_reward
from app.domains.user.models import UserStatus

logger = logging.getLogger(__name__)


class CharacterService:
    def __init__(self, repo: CharacterRepository) -> None:
        self.repo = repo

    def _require_active_user(self, user_id: int) -> None:
        user = self.repo.get_user_by_id(user_id)
        if user is None or user.status != UserStatus.ACTIVE:
            raise InvalidTokenException()

    def get_my_character(self, user_id: int) -> CharacterProfileResponse:
        self._require_active_user(user_id)
        profile = self.repo.get_or_create_by_user_id(user_id)
        owned_animals = self._sync_owned_animals(profile)
        self.repo.db.commit()
        self.repo.db.refresh(profile)
        return self._to_response(profile, owned_animals=owned_animals)

    def gain_exp(
        self,
        user_id: int,
        amount: int,
        reason: str,
        source: str = "internal",
        source_id: str | None = None,
        note: str | None = None,
    ) -> CharacterGainExpResponse:
        """경험치를 획득합니다. 미션/기록 도메인이 호출하는 내부 서비스 seam입니다."""
        self._require_active_user(user_id)
        if amount <= 0:
            raise BadRequestException(
                message="획득 경험치는 1 이상이어야 합니다.", error_code="INVALID_EXP_AMOUNT"
            )

        profile = self.repo.get_or_create_by_user_id_for_update(user_id)
        before_level = profile.level
        before_total_exp = profile.total_exp
        after_total_exp = before_total_exp + amount
        after_level = policy.level_for_total_exp(after_total_exp)

        profile.total_exp = after_total_exp
        profile.level = after_level

        growth_log = self.repo.save_growth_log(
            CharacterGrowthLog(
                character_profile_id=profile.id,
                user_id=user_id,
                exp_gained=amount,
                before_level=before_level,
                after_level=after_level,
                before_total_exp=before_total_exp,
                after_total_exp=after_total_exp,
                reason=reason,
                source=source,
                source_id=source_id,
                note=note,
            )
        )
        growth_log_id = growth_log.id
        owned_animals = self._sync_owned_animals(profile)
        self.repo.db.commit()
        self.repo.db.refresh(profile)
        response = CharacterGainExpResponse(
            profile=self._to_response(profile, owned_animals=owned_animals),
            exp_gained=amount,
            level_before=before_level,
            level_after=after_level,
            leveled_up=after_level > before_level,
        )
        if response.leveled_up:
            self._notify_level_up(
                user_id=user_id,
                growth_log_id=growth_log_id,
                after_level=after_level,
            )
        return response

    def gain_mock_mission_exp(
        self, user_id: int, mission_type: str, mission_id: int | str | None = None
    ) -> CharacterGainExpResponse:
        """미션 생성/API 완성 전까지 쓰는 mock 미션 완료 EXP 지급 seam."""
        reward = calculate_exp_reward(mission_type)
        return self.gain_exp(
            user_id=user_id,
            amount=reward,
            reason="MISSION_COMPLETED",
            source="mock_mission",
            source_id=str(mission_id) if mission_id is not None else None,
            note=f"mock mission_type={mission_type}",
        )

    def list_animals(self, user_id: int) -> list[CharacterCatalogAnimalResponse]:
        self._require_active_user(user_id)
        profile = self.repo.get_or_create_by_user_id(user_id)
        owned_animals = self._sync_owned_animals(profile)
        self.repo.db.commit()
        owned_by_code = {animal.animal_code: animal for animal in owned_animals}
        return [
            CharacterCatalogAnimalResponse(
                animal_code=entry.animal_code,
                name=entry.name,
                unlock_level=entry.unlock_level,
                required_total_exp=entry.required_total_exp,
                image_urls=policy.animal_image_urls(entry.animal_code),
                is_unlocked=entry.animal_code in owned_by_code,
                unlocked_at=owned_by_code[entry.animal_code].unlocked_at
                if entry.animal_code in owned_by_code
                else None,
            )
            for entry in policy.animal_catalog_entries()
        ]

    def _sync_owned_animals(self, profile: CharacterProfile) -> list[CharacterOwnedAnimal]:
        level = policy.level_for_total_exp(profile.total_exp)
        if profile.level != level:
            profile.level = level
        eligible = [
            entry
            for entry in policy.animal_catalog_entries()
            if entry.unlock_level <= profile.level
        ]
        return self.repo.ensure_owned_animals(
            profile, eligible, unlocked_total_exp=profile.total_exp
        )

    def _to_response(
        self,
        profile: CharacterProfile,
        owned_animals: list[CharacterOwnedAnimal] | None = None,
    ) -> CharacterProfileResponse:
        level = policy.level_for_total_exp(profile.total_exp)
        if profile.level != level:
            profile.level = level
        owned_animals = (
            owned_animals if owned_animals is not None else self._sync_owned_animals(profile)
        )
        return CharacterProfileResponse(
            user_id=profile.user_id,
            level=level,
            total_exp=profile.total_exp,
            current_level_exp=policy.current_exp_for_level(profile.total_exp, level),
            exp_to_next_level=policy.exp_required_for_level(level),
            progress_ratio=policy.progress_ratio(profile.total_exp, level),
            owned_animals=[self._owned_animal_response(animal) for animal in owned_animals],
            updated_at=profile.updated_at,
        )

    @staticmethod
    def _owned_animal_response(animal: CharacterOwnedAnimal) -> CharacterOwnedAnimalResponse:
        return CharacterOwnedAnimalResponse(
            animal_code=animal.animal_code,
            name=policy.animal_name_by_code().get(animal.animal_code, animal.animal_code),
            unlocked_level=animal.unlocked_level,
            image_urls=policy.animal_image_urls(animal.animal_code),
            unlocked_at=animal.unlocked_at,
        )

    def _notify_level_up(self, *, user_id: int, growth_log_id: int, after_level: int) -> None:
        from app.domains.notification.repository import NotificationRepository
        from app.domains.notification.service import NotificationService, run_notification_safely

        def notify() -> None:
            NotificationService(NotificationRepository(self.repo.db)).notify_level_up(
                user_id=user_id,
                growth_log_id=growth_log_id,
                after_level=after_level,
                commit=False,
            )

        run_notification_safely(
            self.repo.db,
            notify,
            logger,
            "LEVEL_UP notification failed (user_id=%s, growth_log_id=%s)",
            user_id,
            growth_log_id,
        )
