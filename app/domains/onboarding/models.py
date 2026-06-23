from sqlalchemy import Column, Integer

from app.database.base import Base


class InitialCheckup(Base):
    __tablename__ = "initial_checkups"

    id = Column(Integer, primary_key=True)
    # user_id, raw_data, created_at — Phase 2에서 확정


class WearableDeviceConnection(Base):
    __tablename__ = "wearable_device_connections"

    id = Column(Integer, primary_key=True)
    # user_id, device_type, device_token, connected_at — Phase 2에서 확정
