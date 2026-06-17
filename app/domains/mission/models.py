from sqlalchemy import Column, Integer

from app.database.base import Base


class Mission(Base):
    """미션 원본 정보 (예: 식단 인증하기, 물 마시기)"""

    __tablename__ = "missions"

    id = Column(Integer, primary_key=True)
    # title, description, mission_type, completion_condition, is_active — Phase 4에서 확정


class UserMission(Base):
    """특정 사용자가 특정 날짜에 배정된 미션"""

    __tablename__ = "user_missions"

    id = Column(Integer, primary_key=True)
    # user_id, mission_id, assigned_date, status, completion_type, completed_at — Phase 4에서 확정


class MissionCompletion(Base):
    __tablename__ = "mission_completions"

    id = Column(Integer, primary_key=True)


class MissionStatistics(Base):
    __tablename__ = "mission_statistics"

    id = Column(Integer, primary_key=True)
