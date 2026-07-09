# Media API

앱 정적 이미지(동물 도감, UI 이미지)를 URL 기반으로 제공하는 API입니다.

이미지 원본과 DB import 스크립트는 Git/Docker image에 포함하지 않습니다. 운영자가 SSH로 서버
`/opt/deundeun/media-seed`에 직접 올린 뒤 DB에 seed합니다.

## 저장·접근 정책

| 항목 | 정책 |
|------|------|
| 저장소 | PostgreSQL `image_assets.data` (`bytea`) |
| 대상 | 앱 정적/시스템 이미지 |
| 공개 범위 | 인증 없이 공개 GET |
| 업로드 API | 없음. 운영자 SSH + seed 스크립트로만 등록 |
| 허용 MIME | `image/png`, `image/jpeg`, `image/webp` |
| 최대 크기 | 기본 5MB (`MEDIA_MAX_IMAGE_SIZE_BYTES`) |

검진 OCR 원본, 식단 사진, 사용자 업로드 미디어는 이 API 범위가 아닙니다.

## Endpoints

| Method | Path | 설명 |
|--------|------|------|
| GET | `/api/v1/media/images` | 이미지 메타 목록. `purpose` query filter 지원 |
| GET | `/api/v1/media/images/{image_id}` | 이미지 바이너리 |
| GET | `/api/v1/media/images/{image_id}/meta` | 이미지 메타 |
| GET | `/api/v1/media/images/by-key/{purpose}/{asset_key}` | key 기반 이미지 바이너리 |
| GET | `/api/v1/media/images/by-key/{purpose}/{asset_key}/meta` | key 기반 이미지 메타 |

## 응답 예시

```json
{
  "success": true,
  "message": "요청이 성공했습니다.",
  "data": {
    "id": 1,
    "image_url": "/api/v1/media/images/1",
    "purpose": "animal",
    "asset_key": "frog_1",
    "filename": "frog1.png",
    "content_type": "image/png",
    "byte_size": 709632,
    "sha256": "....",
    "alt_text": "개구리",
    "created_at": "2026-07-09T12:00:00Z"
  },
  "error_code": null
}
```

프론트에서 고정 key를 아는 경우 아래처럼 바로 사용할 수 있습니다.

```html
<img src={`${API_BASE_URL}/api/v1/media/images/by-key/animal/frog_1`} />
```

## 운영 이미지 매핑

| asset key | 파일 |
|-----------|------|
| `animal/frog_1`, `animal/frog_2` | `frog1.png`, `frog2.png` |
| `animal/chick_1`, `animal/chick_2` | `chick1.png`, `chick2.png` |
| `animal/penguin_1`, `animal/penguin_2` | `pan1.png`, `pan2.png` |
| `animal/dog_1`, `animal/dog_2` | `dog1.png`, `dog2.png` |
| `animal/cat_1`, `animal/cat_2` | `cat1.png`, `cat2.png` |
| `animal/tiger_1`, `animal/tiger_2` | `tig1.png`, `tig2.png` |
| `animal/panda_1`, `animal/panda_2` | `bear1.png`, `bear2.png` |
| `animal/monkey_1`, `animal/monkey_2` | `mon1.png`, `mon2.png` |
| `ui/giftbox` | `giftbox.png` |
| `ui/splash_icon` | `splash_Icon.png` |

`.DS_Store`는 seed 대상에서 제외합니다.
