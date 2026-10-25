"""Where uploaded files are kept. Files are named by their SHA-256, so storing twice is harmless.

Only local disk is built so far. An S3-compatible backend can be added later behind the same
four methods (see docs/SDD.md section 8).
"""

import asyncio
import os
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

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


_cache: dict[str, Storage] = {}


def get_storage() -> Storage:
    settings = get_settings()
    if settings.storage_backend != "local":
        raise RuntimeError(f"Storage backend '{settings.storage_backend}' is not built yet")
    key = settings.storage_local_path
    if key not in _cache:
        _cache[key] = LocalStorage(key)
    return _cache[key]
