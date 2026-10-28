"""Where the server address and token are kept. The token can also come from PADDOCK_TOKEN."""

import json
import os
import stat
from pathlib import Path

from .errors import AUTH, USAGE, CliError


def config_path() -> Path:
    if os.environ.get("PADDOCK_CONFIG"):
        return Path(os.environ["PADDOCK_CONFIG"])
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "paddock" / "config.json"


def load() -> dict:
    try:
        return json.loads(config_path().read_text())
    except (OSError, ValueError):
        return {}


def save(url: str, token: str) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"url": url, "token": token}, indent=2) + "\n")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # only you can read it
    return path


def forget() -> bool:
    path = config_path()
    if path.exists():
        path.unlink()
        return True
    return False


def credentials(url_override: str | None = None) -> tuple[str, str]:
    """The API address and token to use. Environment variables win over the saved file."""
    saved = load()
    url = url_override or os.environ.get("PADDOCK_URL") or saved.get("url")
    token = os.environ.get("PADDOCK_TOKEN") or saved.get("token")
    if not url:
        raise CliError("No server address. Run: paddock login --url https://your-paddock", USAGE)
    if not token:
        raise CliError("Not signed in. Run: paddock login (or set PADDOCK_TOKEN)", AUTH)
    return url.rstrip("/"), token
