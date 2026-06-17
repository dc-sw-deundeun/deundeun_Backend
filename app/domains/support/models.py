from sqlalchemy import Column, Integer

from app.database.base import Base


class SupportInquiry(Base):
    __tablename__ = "support_inquiries"

    id = Column(Integer, primary_key=True)
    # user_id, title, content, status, created_at, answered_at
