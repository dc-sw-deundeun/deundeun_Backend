import pytest

from app.infrastructure.storage.file_storage import LocalFileStorage


@pytest.mark.asyncio
async def test_upload_then_read_roundtrip(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    key = await storage.upload("checkups/1/abc.png", b"image-bytes")
    assert key == "checkups/1/abc.png"
    assert await storage.read(key) == b"image-bytes"
    assert await storage.exists(key) is True


@pytest.mark.asyncio
async def test_delete_removes_file(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    key = await storage.upload("a/b.png", b"x")
    await storage.delete(key)
    assert await storage.exists(key) is False


@pytest.mark.asyncio
async def test_read_missing_raises(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    with pytest.raises(FileNotFoundError):
        await storage.read("nope.png")


@pytest.mark.asyncio
async def test_delete_missing_is_ignored(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    await storage.delete("nope.png")  # 예외 없이 통과


@pytest.mark.asyncio
async def test_path_traversal_is_rejected(tmp_path):
    storage = LocalFileStorage(str(tmp_path))
    with pytest.raises(ValueError):
        await storage.read("../escape.png")
    with pytest.raises(ValueError):
        await storage.upload("../escape.png", b"x")
