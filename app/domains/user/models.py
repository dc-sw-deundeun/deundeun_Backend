from sqlalchemy import Column, Integer

from app.database.base import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True)
    # user_id, nickname, profile_image_url, bio — Phase 1에서 확정
