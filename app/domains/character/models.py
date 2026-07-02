from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base
from app.domains.character import policy


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CharacterProfile(Base):
    __tablename__ = "character_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_character_profiles_user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=policy.INITIAL_LEVEL)
    total_exp: Mapped[int] = mapped_column(
        Integer, nullable=False, default=policy.INITIAL_TOTAL_EXP
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    growth_logs: Mapped[list["CharacterGrowthLog"]] = relationship(
        "CharacterGrowthLog", back_populates="character_profile", cascade="all, delete-orphan"
    )
    owned_animals: Mapped[list["CharacterOwnedAnimal"]] = relationship(
        "CharacterOwnedAnimal", back_populates="character_profile", cascade="all, delete-orphan"
    )


class CharacterGrowthLog(Base):
    __tablename__ = "character_growth_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    character_profile_id: Mapped[int] = mapped_column(
        ForeignKey("character_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    exp_gained: Mapped[int] = mapped_column(Integer, nullable=False)
    before_level: Mapped[int] = mapped_column(Integer, nullable=False)
    after_level: Mapped[int] = mapped_column(Integer, nullable=False)
    before_total_exp: Mapped[int] = mapped_column(Integer, nullable=False)
    after_total_exp: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    character_profile: Mapped[CharacterProfile] = relationship(
        "CharacterProfile", back_populates="growth_logs"
    )


class CharacterOwnedAnimal(Base):
    __tablename__ = "character_owned_animals"
    __table_args__ = (
        UniqueConstraint("user_id", "animal_code", name="uq_character_owned_animals_user_animal"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_profile_id: Mapped[int] = mapped_column(
        ForeignKey("character_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    animal_code: Mapped[str] = mapped_column(String(50), nullable=False)
    unlocked_level: Mapped[int] = mapped_column(Integer, nullable=False)
    unlocked_total_exp: Mapped[int] = mapped_column(Integer, nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    character_profile: Mapped[CharacterProfile] = relationship(
        "CharacterProfile", back_populates="owned_animals"
    )
