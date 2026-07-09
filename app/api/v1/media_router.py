from fastapi import APIRouter, Depends, Query, Response

from app.core.dependencies import get_media_service
from app.core.response import success_response
from app.domains.media.models import ImageAsset
from app.domains.media.service import MediaService

router = APIRouter()


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
    purpose: str | None = Query(default=None, min_length=1, max_length=50),
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
    purpose: str,
    asset_key: str,
    service: MediaService = Depends(get_media_service),
):
    return _binary_response(service.get_asset_by_key(purpose, asset_key))


@router.get(
    "/images/by-key/{purpose}/{asset_key}/meta",
    summary="[프론트 사용] 시스템 이미지 key 기반 메타 조회",
    description="purpose와 asset_key로 등록된 시스템 이미지 메타데이터를 조회합니다.",
)
def get_image_meta_by_key(
    purpose: str,
    asset_key: str,
    service: MediaService = Depends(get_media_service),
):
    result = service.get_meta_by_key(purpose, asset_key)
    return success_response(data=result.model_dump(mode="json"))
