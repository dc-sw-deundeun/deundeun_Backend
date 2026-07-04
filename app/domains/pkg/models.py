"""PKG 스냅샷 모델 — 유저당 1행, PKG 객체(JSON)를 통째로 영속한다.

외부 의학 KG(#9, read-only Neo4j 아티팩트)와 물리적으로 분리된 앱 Postgres에 저장한다.
미션 엔진은 PKG를 통짜 객체로 소비하고 저장 그래프를 순회하지 않으므로, 정규화된
nodes/edges 테이블 대신 JSON 스냅샷 1행이면 충분하다. UNIQUE(user_id) + users FK(CASCADE)로
유저 격리와 탈퇴 시 개인건강정보 정리를 스키마 수준에서 강제한다.
"""

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.domains.record.models import CheckupRecord  # noqa: F401
from app.domains.user.models import User  # noqa: F401


class PkgSnapshot(Base):
    __tablename__ = "pkg_snapshots"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_pkg_snapshots_user_id"),
        Index("ix_pkg_snapshots_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_record_id: Mapped[int | None] = mapped_column(
        ForeignKey("checkup_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    built_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
