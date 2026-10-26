"""Where uploaded files are kept. Files are named by their SHA-256, so storing twice is harmless.

Two backends share the same four methods: local disk (development) and any S3-compatible
bucket such as Cloudflare R2, Backblaze B2 or Supabase Storage (hosting, where the disk is
wiped on every restart).
"""

import asyncio
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.core.config import get_settings

CHUNK = 64 * 1024


def storage_key(sha256: str) -> str:
    return f"blobs/{sha256[:2]}/{sha256}"


class Storage(Protocol):
    async def put(self, sha256: str, data: bytes) -> None: ...
    async def exists(self, sha256: str) -> bool: ...
    def open(self, sha256: str) -> AsyncIterator[bytes]: ...
    async def delete(self, sha256: str) -> None: ...


class LocalStorage:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()

    def _path(self, sha256: str) -> Path:
        # sha256 is always 64 hex characters here, so it cannot escape the root.
        if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            raise ValueError("not a sha256 digest")
        return self.root / storage_key(sha256)

    async def put(self, sha256: str, data: bytes) -> None:
        await asyncio.to_thread(self._put, sha256, data)

    def _put(self, sha256: str, data: bytes) -> None:
        path = self._path(sha256)
        if path.exists():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write to a temporary file first so a half-written file is never visible.
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".part-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    async def exists(self, sha256: str) -> bool:
        return await asyncio.to_thread(self._path(sha256).exists)

    async def open(self, sha256: str) -> AsyncIterator[bytes]:  # type: ignore[override]
        path = self._path(sha256)
        handle = await asyncio.to_thread(path.open, "rb")
        try:
            while chunk := await asyncio.to_thread(handle.read, CHUNK):
                yield chunk
        finally:
            handle.close()

    async def delete(self, sha256: str) -> None:
        path = self._path(sha256)
        await asyncio.to_thread(path.unlink, True)


class S3Storage:
    """Stores each file as one object in a bucket. `client` is a boto3 S3 client."""

    def __init__(self, client, bucket: str):
        self.client = client
        self.bucket = bucket

    def _key(self, sha256: str) -> str:
        if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
            raise ValueError("not a sha256 digest")
        return storage_key(sha256)

    async def put(self, sha256: str, data: bytes) -> None:
        key = self._key(sha256)
        await asyncio.to_thread(self.client.put_object, Bucket=self.bucket, Key=key, Body=data)

    async def exists(self, sha256: str) -> bool:
        key = self._key(sha256)
        try:
            await asyncio.to_thread(self.client.head_object, Bucket=self.bucket, Key=key)
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            raise
        return True

    async def open(self, sha256: str) -> AsyncIterator[bytes]:  # type: ignore[override]
        key = self._key(sha256)
        response = await asyncio.to_thread(self.client.get_object, Bucket=self.bucket, Key=key)
        body = response["Body"]
        try:
            while chunk := await asyncio.to_thread(body.read, CHUNK):
                yield chunk
        finally:
            body.close()

    async def delete(self, sha256: str) -> None:
        key = self._key(sha256)
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)


def _s3_client(settings):
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


_cache: dict[str, Storage] = {}


def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend == "s3":
        key = f"s3:{settings.s3_endpoint_url}:{settings.s3_bucket}"
        if key not in _cache:
            _cache[key] = S3Storage(_s3_client(settings), settings.s3_bucket)
        return _cache[key]
    key = settings.storage_local_path
    if key not in _cache:
        _cache[key] = LocalStorage(key)
    return _cache[key]
