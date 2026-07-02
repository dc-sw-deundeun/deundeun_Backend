from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.pkg.models import PkgSnapshot


class PkgRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user(self, user_id: int) -> PkgSnapshot | None:
        return self.db.scalar(select(PkgSnapshot).where(PkgSnapshot.user_id == user_id))

    def upsert_snapshot(
        self, user_id: int, *, payload: dict, source_record_id: int | None
    ) -> PkgSnapshot:
        """유저당 1행 스냅샷을 교체 저장한다(idempotent replace)."""
        snapshot = self.get_by_user(user_id)
        if snapshot is None:
            snapshot = PkgSnapshot(
                user_id=user_id, payload=payload, source_record_id=source_record_id
            )
            self.db.add(snapshot)
        else:
            snapshot.payload = payload
            snapshot.source_record_id = source_record_id
            snapshot.built_at = datetime.now(timezone.utc)
        self.db.flush()
        return snapshot
