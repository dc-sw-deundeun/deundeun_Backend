from sqlalchemy import Column, Integer

from app.database.base import Base


class CharacterProfile(Base):
    __tablename__ = "character_profiles"

    id = Column(Integer, primary_key=True)
    # user_id, stage, exp, level, updated_at — Phase 4에서 확정


class CharacterGrowthLog(Base):
    __tablename__ = "character_growth_logs"

    id = Column(Integer, primary_key=True)
    # character_profile_id, exp_gained, reason, created_at — Phase 4에서 확정
