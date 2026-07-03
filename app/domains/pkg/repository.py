from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domains.pkg.models import PkgSnapshot
from app.domains.user.models import User, UserStatus


class PkgRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user(self, user_id: int) -> PkgSnapshot | None:
        return self.db.scalar(select(PkgSnapshot).where(PkgSnapshot.user_id == user_id))

    def list_snapshot_user_targets(self) -> list[tuple[int, str]]:
        """PKG 스냅샷을 가진 활성 유저의 (user_id, timezone) 목록 — 스케줄러 생성 대상."""
        rows = self.db.execute(
            select(PkgSnapshot.user_id, User.timezone)
            .join(User, User.id == PkgSnapshot.user_id)
            .where(User.status == UserStatus.ACTIVE)
            .order_by(PkgSnapshot.user_id)
        ).all()
        return [(user_id, tz) for user_id, tz in rows]

    def upsert_snapshot(
        self, user_id: int, *, payload: dict, source_record_id: int | None
    ) -> PkgSnapshot:
        """유저당 1행 스냅샷을 원자적으로 교체 저장한다.

        get→insert/update 분기는 동시 요청(GET 조회 + 분석 훅 재빌드)에서 TOCTOU 레이스로
        스냅샷이 유실될 수 있어, Postgres INSERT ... ON CONFLICT(user_id) DO UPDATE로 원자 upsert 한다.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            pg_insert(PkgSnapshot)
            .values(
                user_id=user_id,
                payload=payload,
                source_record_id=source_record_id,
                built_at=now,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={"payload": payload, "source_record_id": source_record_id, "built_at": now},
            )
        )
        self.db.execute(stmt)
        self.db.flush()
        # Core upsert는 ORM identity map을 우회하므로, 이후 조회가 stale 캐시를 보지 않게 만료시킨다.
        self.db.expire_all()
        snapshot = self.get_by_user(user_id)
        assert snapshot is not None  # 방금 upsert 했으므로 항상 존재
        return snapshot
