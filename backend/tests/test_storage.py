import hashlib

import pytest

from app.services.storage import LocalStorage, storage_key


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def read_all(storage, sha):
    return b"".join([chunk async for chunk in storage.open(sha)])


async def test_put_open_exists_delete(tmp_path):
    storage = LocalStorage(tmp_path)
    data = b"hello" * 50_000  # bigger than one chunk
    sha = digest(data)
    assert not await storage.exists(sha)
    await storage.put(sha, data)
    assert await storage.exists(sha)
    assert await read_all(storage, sha) == data
    await storage.delete(sha)
    assert not await storage.exists(sha)
    await storage.delete(sha)  # deleting twice is fine


async def test_put_twice_is_harmless_and_leaves_no_temp_files(tmp_path):
    storage = LocalStorage(tmp_path)
    sha = digest(b"x")
    await storage.put(sha, b"x")
    await storage.put(sha, b"x")
    names = [p.name for p in tmp_path.rglob("*") if p.is_file()]
    assert names == [sha]
    assert storage_key(sha) == f"blobs/{sha[:2]}/{sha}"


@pytest.mark.parametrize("bad", ["../../etc/passwd", "abc", "g" * 64, "A" * 64, ""])
async def test_only_real_digests_are_accepted(tmp_path, bad):
    storage = LocalStorage(tmp_path)
    with pytest.raises(ValueError):
        await storage.put(bad, b"x")
    with pytest.raises(ValueError):
        await storage.exists(bad)
