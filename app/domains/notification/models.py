from sqlalchemy import Column, Integer

from app.database.base import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True)
    # user_id, mission_alarm_enabled, record_alarm_enabled, email_alarm_enabled, push_alarm_enabled


class NotificationLog(Base):
    __tablename__ = "notification_logs"

    id = Column(Integer, primary_key=True)
    # user_id, notification_type, channel, title, content, sent_at, status


class PushToken(Base):
    __tablename__ = "push_tokens"

    id = Column(Integer, primary_key=True)
    # user_id, token, device_type, created_at
