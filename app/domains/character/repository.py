from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domains.character import policy
from app.domains.character.models import CharacterGrowthLog, CharacterOwnedAnimal, CharacterProfile
from app.domains.user.models import User


class CharacterRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_by_id(self, user_id: int) -> User | None:
        return self.db.get(User, user_id)

    def find_by_user_id(self, user_id: int) -> CharacterProfile | None:
        return self.db.scalar(select(CharacterProfile).where(CharacterProfile.user_id == user_id))

    def find_by_user_id_for_update(self, user_id: int) -> CharacterProfile | None:
        return self.db.scalar(
            select(CharacterProfile).where(CharacterProfile.user_id == user_id).with_for_update()
        )

    def get_or_create_by_user_id(self, user_id: int) -> CharacterProfile:
        existing = self.find_by_user_id(user_id)
        if existing is not None:
            return existing

        profile = CharacterProfile(
            user_id=user_id,
            level=policy.INITIAL_LEVEL,
            total_exp=policy.INITIAL_TOTAL_EXP,
        )
        try:
            with self.db.begin_nested():
                self.db.add(profile)
                self.db.flush()
            return profile
        except IntegrityError:
            existing = self.find_by_user_id(user_id)
            if existing is not None:
                return existing
            raise

    def get_or_create_by_user_id_for_update(self, user_id: int) -> CharacterProfile:
        existing = self.find_by_user_id_for_update(user_id)
        if existing is not None:
            return existing

        profile = self.get_or_create_by_user_id(user_id)
        return self.find_by_user_id_for_update(user_id) or profile

    def save_growth_log(self, log: CharacterGrowthLog) -> CharacterGrowthLog:
        self.db.add(log)
        self.db.flush()
        return log

    def latest_growth_log_reason(self, user_id: int, *, source: str, source_id: str) -> str | None:
        """(user_id, source, source_id)의 가장 최근 growth log reason. 없으면 None.

        gain_exp/revoke_exp가 서로 대칭 reason으로 로그를 남기므로, 가장 최근 행의 reason이
        현재 그 이벤트에 대해 XP가 지급된 상태인지(회수되지 않은 상태인지)를 알려준다.
        """
        row = self.db.scalar(
            select(CharacterGrowthLog)
            .where(
                CharacterGrowthLog.user_id == user_id,
                CharacterGrowthLog.source == source,
                CharacterGrowthLog.source_id == source_id,
            )
            .order_by(CharacterGrowthLog.id.desc())
            .limit(1)
        )
        return row.reason if row else None

    def list_owned_animals(self, user_id: int) -> list[CharacterOwnedAnimal]:
        rows = list(
            self.db.scalars(
                select(CharacterOwnedAnimal).where(CharacterOwnedAnimal.user_id == user_id)
            )
        )
        order = policy.animal_order_index()
        return sorted(
            rows, key=lambda row: (order.get(row.animal_code, 10_000), row.unlocked_level)
        )

    def ensure_owned_animals(
        self,
        profile: CharacterProfile,
        catalog_entries: Iterable[policy.AnimalCatalogEntry],
        unlocked_total_exp: int,
    ) -> list[CharacterOwnedAnimal]:
        existing = {animal.animal_code for animal in self.list_owned_animals(profile.user_id)}
        for entry in catalog_entries:
            if entry.animal_code in existing:
                continue
            owned = CharacterOwnedAnimal(
                user_id=profile.user_id,
                character_profile_id=profile.id,
                animal_code=entry.animal_code,
                unlocked_level=entry.unlock_level,
                unlocked_total_exp=(
                    policy.INITIAL_TOTAL_EXP
                    if entry.unlock_level <= policy.INITIAL_LEVEL
                    else unlocked_total_exp
                ),
            )
            try:
                with self.db.begin_nested():
                    self.db.add(owned)
                    self.db.flush()
                existing.add(entry.animal_code)
            except IntegrityError:
                existing = {
                    animal.animal_code for animal in self.list_owned_animals(profile.user_id)
                }
                if entry.animal_code not in existing:
                    raise
        return self.list_owned_animals(profile.user_id)
