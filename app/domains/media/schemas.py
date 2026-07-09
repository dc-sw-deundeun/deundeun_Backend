from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ImageAssetMetaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_url: str
    purpose: str
    asset_key: str
    filename: str
    content_type: str
    byte_size: int
    sha256: str
    alt_text: str | None = None
    created_at: datetime


class ImageAssetListResponse(BaseModel):
    items: list[ImageAssetMetaResponse]
    total: int
