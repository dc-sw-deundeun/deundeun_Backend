from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, defer

from app.domains.media.models import ImageAsset


class MediaRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_assets(self, *, purpose: str | None = None) -> list[ImageAsset]:
        stmt = select(ImageAsset)
        if purpose is not None:
            stmt = stmt.where(ImageAsset.purpose == purpose)
        stmt = stmt.options(defer(ImageAsset.data)).order_by(
            ImageAsset.purpose, ImageAsset.asset_key, ImageAsset.id
        )
        return list(self.db.scalars(stmt))

    def count_assets(self, *, purpose: str | None = None) -> int:
        stmt = select(func.count()).select_from(ImageAsset)
        if purpose is not None:
            stmt = stmt.where(ImageAsset.purpose == purpose)
        return self.db.scalar(stmt) or 0

    def find_by_id(self, image_id: int) -> ImageAsset | None:
        return self.db.get(ImageAsset, image_id)

    def find_by_key(self, *, purpose: str, asset_key: str) -> ImageAsset | None:
        return self.db.scalar(
            select(ImageAsset).where(
                ImageAsset.purpose == purpose,
                ImageAsset.asset_key == asset_key,
            )
        )

    def upsert_system_asset(
        self,
        *,
        purpose: str,
        asset_key: str,
        filename: str,
        content_type: str,
        byte_size: int,
        sha256: str,
        data: bytes,
        alt_text: str | None = None,
    ) -> ImageAsset:
        stmt = (
            pg_insert(ImageAsset)
            .values(
                purpose=purpose,
                asset_key=asset_key,
                filename=filename,
                content_type=content_type,
                byte_size=byte_size,
                sha256=sha256,
                data=data,
                alt_text=alt_text,
            )
            .on_conflict_do_update(
                constraint="uq_image_assets_purpose_asset_key",
                set_={
                    "filename": filename,
                    "content_type": content_type,
                    "byte_size": byte_size,
                    "sha256": sha256,
                    "data": data,
                    "alt_text": alt_text,
                },
            )
            .returning(ImageAsset)
        )
        return self.db.execute(stmt).scalars().one()
