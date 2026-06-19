from typing import Protocol


class FileStorage(Protocol):
    """파일 저장소 인터페이스입니다. 로컬 스토리지 → AWS S3 등으로 교체 가능합니다."""

    async def upload(self, file_path: str, content: bytes) -> str:
        """파일을 업로드하고 접근 URL을 반환합니다."""
        ...

    async def delete(self, file_path: str) -> None: ...


class StubFileStorage:
    """개발/테스트용 stub 구현입니다."""

    async def upload(self, file_path: str, content: bytes) -> str:
        raise NotImplementedError

    async def delete(self, file_path: str) -> None:
        raise NotImplementedError
