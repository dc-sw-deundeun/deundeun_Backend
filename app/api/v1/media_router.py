from fastapi import APIRouter, Depends, Path, Query, Response

from app.core.dependencies import get_media_service
from app.core.response import success_response
from app.domains.media.models import ImageAsset
from app.domains.media.service import MediaService

router = APIRouter()

MEDIA_PURPOSE_DESCRIPTION = (
    "이미지 사용 목적입니다. 현재 운영 seed 기준 허용 값: "
    "`animal`(동물 도감), `ui`(앱 UI 이미지)."
)
MEDIA_ASSET_KEY_DESCRIPTION = (
    "purpose별 이미지 key입니다. 예: "
    "animal은 `frog_1`, `frog_2`, `chick_1`, `chick_2`, "
    "`penguin_1`, `penguin_2`, `dog_1`, `dog_2`, `cat_1`, `cat_2`, "
    "`tiger_1`, `tiger_2`, `panda_1`, `panda_2`, `monkey_1`, `monkey_2`; "
    "ui는 `giftbox`, `splash_icon`."
)


def _binary_response(asset: ImageAsset) -> Response:
    return Response(
        content=asset.data,
        media_type=asset.content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "ETag": f'"{asset.sha256}"',
        },
    )


@router.get(
    "/images",
    summary="[프론트 사용] 시스템 이미지 목록 조회",
    description=(
        "서버 DB에 등록된 앱 정적 이미지 메타 목록을 조회합니다. "
        "이미지 파일과 seed 스크립트는 Git/Docker에 포함하지 않고 운영자가 SSH로 등록합니다."
    ),
)
def list_images(
    purpose: str | None = Query(
        default=None,
        min_length=1,
        max_length=50,
        description=MEDIA_PURPOSE_DESCRIPTION,
        examples=["animal", "ui"],
    ),
    service: MediaService = Depends(get_media_service),
):
    result = service.list_assets(purpose=purpose)
    return success_response(data=result.model_dump(mode="json"))


@router.get(
    "/images/{image_id}",
    summary="[프론트 사용] 시스템 이미지 바이너리 조회",
    description="이미지 ID로 PNG/JPEG/WebP 바이너리를 반환합니다. 시스템 이미지는 인증 없이 조회 가능합니다.",
)
def get_image(
    image_id: int,
    service: MediaService = Depends(get_media_service),
):
    return _binary_response(service.get_asset(image_id))


@router.get(
    "/images/{image_id}/meta",
    summary="[프론트 사용] 시스템 이미지 메타 조회",
    description="이미지 ID로 파일명, MIME, 크기, sha256, URL 등 메타데이터를 조회합니다.",
)
def get_image_meta(
    image_id: int,
    service: MediaService = Depends(get_media_service),
):
    result = service.get_meta(image_id)
    return success_response(data=result.model_dump(mode="json"))


@router.get(
    "/images/by-key/{purpose}/{asset_key}",
    summary="[프론트 사용] 시스템 이미지 key 기반 바이너리 조회",
    description="동물 도감처럼 고정 key를 아는 화면에서 바로 `<img src>`로 사용할 수 있는 공개 이미지 URL입니다.",
)
def get_image_by_key(
    purpose: str = Path(
        min_length=1,
        max_length=50,
        description=MEDIA_PURPOSE_DESCRIPTION,
        examples=["animal", "ui"],
    ),
    asset_key: str = Path(
        min_length=1,
        max_length=100,
        description=MEDIA_ASSET_KEY_DESCRIPTION,
        examples=["frog_1", "giftbox"],
    ),
    service: MediaService = Depends(get_media_service),
):
    return _binary_response(service.get_asset_by_key(purpose, asset_key))


@router.get(
    "/images/by-key/{purpose}/{asset_key}/meta",
    summary="[프론트 사용] 시스템 이미지 key 기반 메타 조회",
    description="purpose와 asset_key로 등록된 시스템 이미지 메타데이터를 조회합니다.",
)
def get_image_meta_by_key(
    purpose: str = Path(
        min_length=1,
        max_length=50,
        description=MEDIA_PURPOSE_DESCRIPTION,
        examples=["animal", "ui"],
    ),
    asset_key: str = Path(
        min_length=1,
        max_length=100,
        description=MEDIA_ASSET_KEY_DESCRIPTION,
        examples=["frog_1", "giftbox"],
    ),
    service: MediaService = Depends(get_media_service),
):
    result = service.get_meta_by_key(purpose, asset_key)
    return success_response(data=result.model_dump(mode="json"))
