"""Checks on uploaded files. Nothing here touches the database or storage.

A bundle is a set of files that make up one version of a page (SDD section 5.1).
Every rule exists to keep one person's page from harming the server or another person.
"""

import hashlib
import json
import re
from dataclasses import dataclass

from app.core.config import Settings
from app.core.errors import AppError

PATH_PATTERN = re.compile(r"^[a-z0-9._-]+(/[a-z0-9._-]+)*$")
MAX_PATH_LENGTH = 200

# extension -> content type. Anything else is refused.
TYPES = {
    "html": "text/html; charset=utf-8",
    "htm": "text/html; charset=utf-8",
    "css": "text/css; charset=utf-8",
    "js": "text/javascript; charset=utf-8",
    "mjs": "text/javascript; charset=utf-8",
    "json": "application/json",
    "txt": "text/plain; charset=utf-8",
    "svg": "image/svg+xml",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "avif": "image/avif",
    "ico": "image/x-icon",
    "woff": "font/woff",
    "woff2": "font/woff2",
    "ttf": "font/ttf",
    "otf": "font/otf",
    "mp4": "video/mp4",
    "webm": "video/webm",
}
TEXT_EXTENSIONS = {"html", "htm", "css", "js", "mjs", "json", "txt", "svg"}
HTML_EXTENSIONS = {"html", "htm"}


@dataclass
class IncomingFile:
    path: str
    data: bytes
    claimed_sha256: str | None = None  # from the client's manifest, if given


@dataclass
class CheckedFile:
    path: str
    data: bytes
    sha256: str
    size: int
    content_type: str


def normalise_path(raw: str) -> str:
    """Return a clean relative path, or refuse it."""
    path = raw.strip().replace("\\", "/")
    if path.startswith("./"):
        path = path[2:]
    path = path.lower()
    if not path or len(path) > MAX_PATH_LENGTH:
        raise AppError(422, "validation_failed", f"Invalid file path: {raw[:60]!r}")
    if (
        path.startswith("/")
        or "//" in path
        or any(part in ("", ".", "..") for part in path.split("/"))
    ):
        raise AppError(422, "validation_failed", f"Invalid file path: {raw[:60]!r}")
    if not PATH_PATTERN.match(path):
        raise AppError(
            422,
            "validation_failed",
            f"File path {raw[:60]!r} may only use letters, digits, dots, dashes, "
            "underscores and slashes",
        )
    return path


def extension(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    return name.rsplit(".", 1)[-1] if "." in name else ""


def _starts(data: bytes, *prefixes: bytes) -> bool:
    return any(data.startswith(p) for p in prefixes)


def content_matches(ext: str, data: bytes) -> bool:
    """Check the bytes really look like what the extension says."""
    if ext in TEXT_EXTENSIONS:
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            return False
        if "\x00" in text:
            return False
        if ext == "json":
            try:
                json.loads(text)
            except ValueError:
                return False
        if ext == "svg":
            return "<svg" in text.lower()
        return True
    if ext == "png":
        return _starts(data, b"\x89PNG\r\n\x1a\n")
    if ext in ("jpg", "jpeg"):
        return _starts(data, b"\xff\xd8\xff")
    if ext == "gif":
        return _starts(data, b"GIF87a", b"GIF89a")
    if ext == "webp":
        return data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    if ext == "avif":
        return data[4:8] == b"ftyp" and data[8:12] in (b"avif", b"avis")
    if ext == "ico":
        return _starts(data, b"\x00\x00\x01\x00")
    if ext == "woff":
        return _starts(data, b"wOFF")
    if ext == "woff2":
        return _starts(data, b"wOF2")
    if ext == "ttf":
        return _starts(data, b"\x00\x01\x00\x00", b"true")
    if ext == "otf":
        return _starts(data, b"OTTO")
    if ext == "mp4":
        return data[4:8] == b"ftyp"
    if ext == "webm":
        return _starts(data, b"\x1a\x45\xdf\xa3")
    return False


def check_bundle(
    files: list[IncomingFile], entry_path: str | None, settings: Settings
) -> tuple[list[CheckedFile], str]:
    """Validate a whole bundle. Returns the checked files and the entry path."""
    if not files:
        raise AppError(422, "validation_failed", "Upload at least one file")
    if len(files) > settings.max_files:
        raise AppError(
            413, "payload_too_large", f"A bundle can hold at most {settings.max_files} files"
        )

    # A single HTML file with no index.html becomes index.html.
    if len(files) == 1 and extension(files[0].path.lower()) in HTML_EXTENSIONS:
        only = files[0]
        if "/" not in only.path.replace("\\", "/") and only.path.lower() != "index.html":
            files = [IncomingFile("index.html", only.data, only.claimed_sha256)]

    checked: dict[str, CheckedFile] = {}
    total = 0
    for item in files:
        path = normalise_path(item.path)
        if path in checked:
            raise AppError(422, "validation_failed", f"The path {path!r} appears more than once")
        size = len(item.data)
        if size > settings.max_file_bytes:
            raise AppError(
                413, "payload_too_large", f"{path} is larger than {settings.max_file_bytes} bytes"
            )
        total += size
        if total > settings.max_bundle_bytes:
            raise AppError(
                413,
                "payload_too_large",
                f"A bundle can be at most {settings.max_bundle_bytes} bytes",
            )
        ext = extension(path)
        if ext not in TYPES:
            raise AppError(
                415, "unsupported_media", f"Files of type .{ext or '(none)'} are not allowed"
            )
        if not content_matches(ext, item.data):
            raise AppError(
                415, "unsupported_media", f"{path} does not look like a real .{ext} file"
            )
        digest = hashlib.sha256(item.data).hexdigest()
        if item.claimed_sha256 and item.claimed_sha256.lower() != digest:
            raise AppError(
                422, "validation_failed", f"The checksum for {path} does not match its content"
            )
        checked[path] = CheckedFile(path, item.data, digest, size, TYPES[ext])

    entry = normalise_path(entry_path) if entry_path else "index.html"
    if entry not in checked:
        raise AppError(422, "validation_failed", f"The entry file {entry!r} is not in the bundle")
    if extension(entry) not in HTML_EXTENSIONS:
        raise AppError(422, "validation_failed", "The entry file must be an HTML file")
    return sorted(checked.values(), key=lambda f: f.path), entry


def fingerprint(files: list[tuple[str, str]], entry: str) -> str:
    """A hash of the file set and entry file, used to spot a repeat publish."""
    lines = [f"entry:{entry}"] + [f"{path}:{sha}" for path, sha in sorted(files)]
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()
