"""Read an upload from a request. Two shapes are accepted:

1. multipart/form-data: text fields plus one or more `files` parts. A part's filename is its
   path in the bundle (for example `assets/app.js`). An optional `manifest` field lists
   {path, sha256} pairs so the server can verify every file.
2. application/json: {"files": [{"path", "content", "encoding"}], ...} where encoding is
   "utf-8" (default) or "base64". Easier for agents sending small pages.
"""

import base64
import binascii
import json
from dataclasses import dataclass, field

from fastapi import Request
from pydantic import BaseModel, Field, ValidationError
from starlette.datastructures import UploadFile

from app.core.config import get_settings
from app.core.errors import AppError
from app.services.bundles import IncomingFile, normalise_path

OVERHEAD = 1024 * 1024  # room for form fields and part headers


@dataclass
class BundleRequest:
    fields: dict[str, str] = field(default_factory=dict)
    files: list[IncomingFile] = field(default_factory=list)


class _JsonFile(BaseModel):
    path: str = Field(min_length=1, max_length=300)
    content: str
    encoding: str = "utf-8"


def _too_large(limit: int) -> AppError:
    return AppError(413, "payload_too_large", f"The upload is larger than {limit} bytes")


async def read_bundle_request(request: Request) -> BundleRequest:
    settings = get_settings()
    limit = settings.max_bundle_bytes
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit * 2 + OVERHEAD:
        raise _too_large(limit)

    kind = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if kind == "multipart/form-data":
        return await _read_multipart(request, settings.max_file_bytes, settings.max_files)
    if kind == "application/json":
        return await _read_json(request, limit)
    raise AppError(415, "unsupported_media", "Send multipart/form-data or application/json")


async def _read_multipart(request: Request, max_file: int, max_files: int) -> BundleRequest:
    form = await request.form(max_files=max_files + 1, max_fields=50)
    result = BundleRequest()
    manifest: dict[str, str] = {}
    for key, value in form.multi_items():
        if isinstance(value, UploadFile):
            if key != "files":
                raise AppError(
                    422, "validation_failed", f"Unexpected file part '{key}'. Use 'files'."
                )
            if not value.filename:
                raise AppError(
                    422, "validation_failed", "Every file part needs a filename (its path)"
                )
            data = await value.read(max_file + 1)
            result.files.append(IncomingFile(path=value.filename, data=data))
        elif key == "manifest":
            manifest = _read_manifest(str(value))
        else:
            result.fields[key] = str(value)

    if manifest:
        seen = set()
        for item in result.files:
            path = normalise_path(item.path)
            seen.add(path)
            item.claimed_sha256 = manifest.get(path)
        missing = set(manifest) - seen
        if missing:
            raise AppError(
                422,
                "validation_failed",
                f"The manifest lists {sorted(missing)[0]} but it was not uploaded",
            )
    return result


def _read_manifest(raw: str) -> dict[str, str]:
    try:
        items = json.loads(raw)
        return {normalise_path(i["path"]): str(i["sha256"]).lower() for i in items}
    except AppError:
        raise
    except (ValueError, KeyError, TypeError):
        raise AppError(
            422, "validation_failed", "The manifest must be a JSON list of {path, sha256}"
        ) from None


def decode_file(path: str, content: str, encoding: str = "utf-8") -> IncomingFile:
    """Turn one {path, content, encoding} item into file bytes. Shared with the MCP tools."""
    if encoding == "base64":
        try:
            data = base64.b64decode(content, validate=True)
        except (binascii.Error, ValueError):
            raise AppError(422, "validation_failed", f"{path}: invalid base64") from None
    elif encoding in ("utf-8", "utf8"):
        data = content.encode()
    else:
        raise AppError(422, "validation_failed", "encoding must be 'utf-8' or 'base64'")
    return IncomingFile(path=path, data=data)


async def _read_json(request: Request, limit: int) -> BundleRequest:
    body = await request.body()
    if len(body) > limit * 2 + OVERHEAD:
        raise _too_large(limit)
    try:
        data = json.loads(body)
    except ValueError:
        raise AppError(422, "validation_failed", "The body is not valid JSON") from None
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        raise AppError(422, "validation_failed", "Expected an object with a 'files' list")

    result = BundleRequest()
    for raw in data["files"]:
        try:
            item = _JsonFile.model_validate(raw)
        except ValidationError as exc:
            raise AppError(422, "validation_failed", f"files: {exc.errors()[0]['msg']}") from None
        result.files.append(decode_file(item.path, item.content, item.encoding))
    result.fields = {k: str(v) for k, v in data.items() if k != "files" and v is not None}
    return result
