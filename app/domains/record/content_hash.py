import hashlib


def compute_content_hash(images: list[bytes]) -> str:
    """업로드 이미지 bytes 결합 SHA-256 (서버 저장 없이 중복 방지용)."""
    digest = hashlib.sha256()
    for chunk in images:
        digest.update(chunk)
    return digest.hexdigest()
