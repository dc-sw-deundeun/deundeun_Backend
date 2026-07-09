import hashlib

from app.core.config import settings
from app.core.exceptions import (
    NotFoundException,
    PayloadTooLargeException,
    UnsupportedMediaTypeException,
)
from app.domains.media.models import ImageAsset
from app.domains.media.repository import MediaRepository
from app.domains.media.schemas import ImageAssetListResponse, ImageAssetMetaResponse

ALLOWED_IMAGE_CONTENT_TYPES = {"image/png", "image/jpeg", "image/webp"}


class MediaService:
    def __init__(self, repo: MediaRepository) -> None:
        self.repo = repo

    def list_assets(self, purpose: str | None = None) -> ImageAssetListResponse:
        assets = self.repo.list_assets(purpose=purpose)
        return ImageAssetListResponse(
            items=[self._to_meta(asset) for asset in assets],
            total=self.repo.count_assets(purpose=purpose),
        )

    def get_asset(self, image_id: int) -> ImageAsset:
        asset = self.repo.find_by_id(image_id)
        if asset is None:
            raise NotFoundException(
                message="이미지를 찾을 수 없습니다.", error_code="IMAGE_ASSET_NOT_FOUND"
            )
        return asset

    def get_asset_by_key(self, purpose: str, asset_key: str) -> ImageAsset:
        asset = self.repo.find_by_key(purpose=purpose, asset_key=asset_key)
        if asset is None:
            raise NotFoundException(
                message="이미지를 찾을 수 없습니다.", error_code="IMAGE_ASSET_NOT_FOUND"
            )
        return asset

    def get_meta(self, image_id: int) -> ImageAssetMetaResponse:
        return self._to_meta(self.get_asset(image_id))

    def get_meta_by_key(self, purpose: str, asset_key: str) -> ImageAssetMetaResponse:
        return self._to_meta(self.get_asset_by_key(purpose, asset_key))

    def upsert_system_asset(
        self,
        *,
        purpose: str,
        asset_key: str,
        filename: str,
        content_type: str,
        data: bytes,
        alt_text: str | None = None,
    ) -> ImageAsset:
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise UnsupportedMediaTypeException()
        if len(data) > settings.media_max_image_size_bytes:
            raise PayloadTooLargeException()
        return self.repo.upsert_system_asset(
            purpose=purpose,
            asset_key=asset_key,
            filename=filename,
            content_type=content_type,
            byte_size=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            data=data,
            alt_text=alt_text,
        )

    @staticmethod
    def image_url(asset: ImageAsset) -> str:
        return f"/api/v1/media/images/{asset.id}"

    @classmethod
    def _to_meta(cls, asset: ImageAsset) -> ImageAssetMetaResponse:
        return ImageAssetMetaResponse(
            id=asset.id,
            image_url=cls.image_url(asset),
            purpose=asset.purpose,
            asset_key=asset.asset_key,
            filename=asset.filename,
            content_type=asset.content_type,
            byte_size=asset.byte_size,
            sha256=asset.sha256,
            alt_text=asset.alt_text,
            created_at=asset.created_at,
        )
