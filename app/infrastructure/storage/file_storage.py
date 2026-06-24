import asyncio
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
        self._base = Path(base_dir).resolve()

    def _full(self, file_path: str) -> Path:
        # base 디렉터리 밖으로의 경로 탈출(../)을 차단한다.
        full = (self._base / file_path).resolve()
        if full != self._base and self._base not in full.parents:
            raise ValueError(f"경로가 기준 디렉터리를 벗어났습니다: {file_path}")
        return full

    def _upload_sync(self, full: Path, content: bytes) -> None:
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(content)

    async def upload(self, file_path: str, content: bytes) -> str:
        full = self._full(file_path)
        await asyncio.to_thread(self._upload_sync, full, content)
        return file_path

    async def read(self, file_path: str) -> bytes:
        full = self._full(file_path)
        return await asyncio.to_thread(full.read_bytes)

    async def delete(self, file_path: str) -> None:
        full = self._full(file_path)
        await asyncio.to_thread(full.unlink, missing_ok=True)

    async def exists(self, file_path: str) -> bool:
        full = self._full(file_path)
        return await asyncio.to_thread(full.is_file)


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
