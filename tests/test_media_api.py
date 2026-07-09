from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import PayloadTooLargeException, UnsupportedMediaTypeException
from app.domains.media.models import ImageAsset
from app.domains.media.repository import MediaRepository
from app.domains.media.service import MediaService


def _seed_image(
    db_session: Session,
    *,
    purpose: str = "animal",
    asset_key: str = "frog_1",
    filename: str = "frog1.png",
    data: bytes = b"png-data",
) -> ImageAsset:
    asset = MediaService(MediaRepository(db_session)).upsert_system_asset(
        purpose=purpose,
        asset_key=asset_key,
        filename=filename,
        content_type="image/png",
        data=data,
        alt_text="개구리",
    )
    db_session.commit()
    db_session.refresh(asset)
    return asset


def test_media_image_by_key_is_public_and_returns_binary(
    client: TestClient, db_session: Session
) -> None:
    asset = _seed_image(db_session)

    res = client.get("/api/v1/media/images/by-key/animal/frog_1")

    assert res.status_code == 200
    assert res.content == b"png-data"
    assert res.headers["content-type"] == "image/png"
    assert res.headers["etag"] == f'"{asset.sha256}"'
    assert res.headers["cache-control"] == "public, max-age=86400"


def test_media_meta_and_list_endpoints(client: TestClient, db_session: Session) -> None:
    asset = _seed_image(db_session)
    _seed_image(
        db_session,
        purpose="ui",
        asset_key="giftbox",
        filename="giftbox.png",
        data=b"giftbox",
    )

    list_res = client.get("/api/v1/media/images", params={"purpose": "animal"})
    meta_res = client.get(f"/api/v1/media/images/{asset.id}/meta")
    key_meta_res = client.get("/api/v1/media/images/by-key/animal/frog_1/meta")

    assert list_res.status_code == 200
    assert list_res.json()["data"]["total"] == 1
    assert list_res.json()["data"]["items"][0]["asset_key"] == "frog_1"

    assert meta_res.status_code == 200
    assert meta_res.json()["data"]["image_url"] == f"/api/v1/media/images/{asset.id}"
    assert meta_res.json()["data"]["sha256"] == asset.sha256

    assert key_meta_res.status_code == 200
    assert key_meta_res.json()["data"]["id"] == asset.id


def test_media_unknown_key_returns_404(client: TestClient) -> None:
    res = client.get("/api/v1/media/images/by-key/animal/missing")

    assert res.status_code == 404
    assert res.json()["error_code"] == "IMAGE_ASSET_NOT_FOUND"


def test_media_upsert_is_idempotent(db_session: Session) -> None:
    first = _seed_image(db_session, data=b"old")
    second = _seed_image(db_session, data=b"new")

    count = db_session.scalar(select(func.count()).select_from(ImageAsset))
    assert count == 1
    assert second.id == first.id
    assert second.data == b"new"


def test_media_service_rejects_invalid_type_and_oversize(db_session: Session) -> None:
    service = MediaService(MediaRepository(db_session))

    try:
        service.upsert_system_asset(
            purpose="animal",
            asset_key="frog_1",
            filename="frog.gif",
            content_type="image/gif",
            data=b"gif",
        )
    except UnsupportedMediaTypeException:
        pass
    else:
        raise AssertionError("expected UnsupportedMediaTypeException")

    original_limit = settings.media_max_image_size_bytes
    settings.media_max_image_size_bytes = 2
    try:
        try:
            service.upsert_system_asset(
                purpose="animal",
                asset_key="frog_1",
                filename="frog.png",
                content_type="image/png",
                data=b"too-large",
            )
        except PayloadTooLargeException:
            pass
        else:
            raise AssertionError("expected PayloadTooLargeException")
    finally:
        settings.media_max_image_size_bytes = original_limit
