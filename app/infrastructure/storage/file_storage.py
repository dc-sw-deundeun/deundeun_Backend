from pathlib import Path
from typing import Protocol


class FileStorage(Protocol):
    """파일 저장소 인터페이스입니다. 로컬 임시 저장 → 필요 시 S3 등으로 교체 가능합니다."""

    async def upload(self, file_path: str, content: bytes) -> str:
        """파일을 저장하고 접근 key를 반환합니다."""
        ...

    async def read(self, file_path: str) -> bytes: ...

    async def delete(self, file_path: str) -> None: ...

    async def exists(self, file_path: str) -> bool: ...


class LocalFileStorage:
    """로컬 디스크 임시 저장 구현입니다. base_dir 하위에 key 경로로 저장합니다."""

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir)

    def _full(self, file_path: str) -> Path:
        return self._base / file_path

    async def upload(self, file_path: str, content: bytes) -> str:
        full = self._full(file_path)
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(content)
        return file_path

    async def read(self, file_path: str) -> bytes:
        return self._full(file_path).read_bytes()

    async def delete(self, file_path: str) -> None:
        self._full(file_path).unlink(missing_ok=True)

    async def exists(self, file_path: str) -> bool:
        return self._full(file_path).is_file()


class StubFileStorage:
    """개발/테스트용 stub 구현입니다."""

    async def upload(self, file_path: str, content: bytes) -> str:
        return file_path

    async def read(self, file_path: str) -> bytes:
        return b""

    async def delete(self, file_path: str) -> None:
        return None

    async def exists(self, file_path: str) -> bool:
        return True
