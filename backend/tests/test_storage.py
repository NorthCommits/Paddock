import hashlib
import io

import pytest
from botocore.exceptions import ClientError

from app.core.config import Settings
from app.services.storage import LocalStorage, S3Storage, storage_key


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


class FakeS3:
    """Just enough of a boto3 S3 client to test S3Storage without a network."""

    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body):
        self.objects[(Bucket, Key)] = Body

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)


async def test_s3_put_read_delete():
    client = FakeS3()
    storage = S3Storage(client, "bucket")
    data = b"hello" * 50000
    sha = hashlib.sha256(data).hexdigest()
    assert not await storage.exists(sha)
    await storage.put(sha, data)
    assert ("bucket", storage_key(sha)) in client.objects
    assert await storage.exists(sha)
    assert await read_all(storage, sha) == data
    await storage.delete(sha)
    assert not await storage.exists(sha)
    await storage.delete(sha)


async def test_s3_rejects_bad_digest():
    storage = S3Storage(FakeS3(), "bucket")
    with pytest.raises(ValueError):
        await storage.put("../etc/passwd", b"x")


def test_s3_settings_need_all_values():
    with pytest.raises(ValueError):
        Settings(database_url="postgresql+asyncpg://x/y", storage_backend="s3", _env_file=None)
    Settings(
        database_url="postgresql+asyncpg://x/y",
        storage_backend="s3",
        s3_bucket="b",
        s3_endpoint_url="https://example.test",
        s3_access_key_id="id",
        s3_secret_access_key="secret",
        _env_file=None,
    )
