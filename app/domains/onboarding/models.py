import enum
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.domains.user.models import User


class WearableProvider(str, enum.Enum):
    """지원 웨어러블/헬스 플랫폼.

    네이티브 모바일 앱(iOS/Android) 기준이며, iOS는 Apple Health(HealthKit),
    Android는 삼성헬스·Google Fit(Health Connect)을 통해 연동한다.
    HealthKit은 서버용 API가 없어 앱이 온디바이스에서 권한을 처리하고,
    백엔드는 연결 상태와 승인된 scope만 보관한다.
    """

    APPLE_HEALTH = "APPLE_HEALTH"
    SAMSUNG_HEALTH = "SAMSUNG_HEALTH"
    GOOGLE_FIT = "GOOGLE_FIT"


class WearableStatus(str, enum.Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class WearableConnection(Base):
    """사용자별 웨어러블/헬스 플랫폼 연결 상태.

    실제 건강 데이터 수신(앱 → 백엔드 push)은 후속 Phase에서 다룬다.
    여기서는 온보딩에 필요한 연결 상태와 승인 scope만 보관한다.
    """

    __tablename__ = "wearable_connections"
    __table_args__ = (
        UniqueConstraint("user_id", "provider", name="uq_wearable_connections_user_provider"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        Enum(WearableProvider, name="wearable_provider_enum"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        Enum(WearableStatus, name="wearable_status_enum"),
        nullable=False,
    )
    scopes: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")
