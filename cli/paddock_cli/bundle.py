"""Turn a file or a folder into the parts of an upload."""

import hashlib
import json
import mimetypes
from pathlib import Path

from .errors import USAGE, CliError

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".idea", ".vscode"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


def collect(target: str) -> list[tuple[str, bytes]]:
    """Return (path in the bundle, bytes). A single HTML file is published as index.html."""
    path = Path(target)
    if not path.exists():
        raise CliError(f"{target} does not exist", USAGE)
    if path.is_file():
        if path.suffix.lower() not in (".html", ".htm"):
            raise CliError("Give an .html file, or a folder that contains index.html", USAGE)
        return [("index.html", path.read_bytes())]
    found = []
    for item in sorted(path.rglob("*")):
        rel = item.relative_to(path)
        if not item.is_file() or item.name in SKIP_FILES or SKIP_DIRS & set(rel.parts[:-1]):
            continue
        found.append((rel.as_posix(), item.read_bytes()))
    if not found:
        raise CliError(f"{target} has no files", USAGE)
    return found


def multipart(files: list[tuple[str, bytes]]) -> tuple[list, str]:
    """The `files` parts and a manifest the server uses to check every file arrived intact."""
    parts = [
        ("files", (name, data, mimetypes.guess_type(name)[0] or "application/octet-stream"))
        for name, data in files
    ]
    manifest = json.dumps(
        [{"path": name, "sha256": hashlib.sha256(data).hexdigest()} for name, data in files]
    )
    return parts, manifest
