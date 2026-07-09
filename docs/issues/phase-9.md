# Phase 9: 앱 미디어/정적 이미지 제공

## 목표

프론트가 동물 도감과 앱 UI 이미지를 URL로 렌더링할 수 있게 Media API를 제공합니다.

## 범위

- `image_assets` DB 테이블 추가
- 시스템 이미지 공개 조회 API 추가
- Character API 응답에 `image_urls` 추가
- 운영자가 SSH로 이미지와 seed 스크립트를 서버에 직접 업로드하는 절차 문서화

## 제외

- 이미지 원본 Git 커밋
- Docker image에 이미지 포함
- 운영용 multipart 업로드 API
- 사용자 업로드 미디어, 검진 OCR 원본 저장, S3/MinIO/CDN

## 운영 원칙

- 서버 원본 위치: `/opt/deundeun/media-seed/images`
- 서버 seed 스크립트 위치: `/opt/deundeun/media-seed/seed_app_images.py`
- DB import 후에도 원본 이미지와 seed 스크립트는 서버에 남겨 재실행 가능하게 합니다.

## 완료 기준

- `/api/v1/media/images/by-key/animal/frog_1` 같은 공개 이미지 URL이 동작합니다.
- `/api/v1/characters/animals`와 `/api/v1/characters/me`에 `image_urls`가 포함됩니다.
- `ruff`, `mypy`, `pytest`, `alembic check`, Docker build가 통과합니다.
