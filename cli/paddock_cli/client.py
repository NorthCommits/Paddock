"""A thin client over the public API. It adds no logic the API does not have."""

import json
import time
from collections.abc import Iterator

import httpx

from .errors import AUTH, CONFLICT, GENERAL, CliError

RETRIES = 2  # extra tries when the API says slow down (429)


def find_base(url: str, transport: httpx.BaseTransport | None = None) -> str:
    """The frontend forwards the API under /api, while the API itself has no prefix. Try both."""
    url = url.rstrip("/")
    with httpx.Client(timeout=20, transport=transport) as http:
        for base in (url, url + "/api"):
            try:
                res = http.get(base + "/v1/me")
            except httpx.HTTPError as err:
                raise CliError(f"Cannot reach {url}: {err}") from None
            if res.headers.get("content-type", "").startswith("application/json"):
                return base
    raise CliError(f"{url} does not look like a Paddock server")


class Client:
    def __init__(self, base: str, token: str, transport: httpx.BaseTransport | None = None):
        self.base = base.rstrip("/")
        self.http = httpx.Client(
            base_url=self.base,
            headers={"Authorization": f"Bearer {token}", "User-Agent": "paddock-cli"},
            timeout=60,
            transport=transport,
        )

    @property
    def site(self) -> str | None:
        """The address people open in a browser, when it can be told from the API address."""
        return self.base[: -len("/api")] if self.base.endswith("/api") else None

    def request(self, method: str, path: str, **kwargs):
        for attempt in range(RETRIES + 1):
            try:
                res = self.http.request(method, path, **kwargs)
            except httpx.HTTPError as err:
                raise CliError(f"Cannot reach Paddock: {err}") from None
            if res.status_code == 429 and attempt < RETRIES:
                time.sleep(min(int(res.headers.get("retry-after", "2") or 2), 30))
                continue
            break
        if res.status_code == 204:
            return None
        try:
            data = res.json()
        except ValueError:
            data = None
        if res.is_success:
            return data
        error = (data or {}).get("error", {}) if isinstance(data, dict) else {}
        message = error.get("message") or f"The server answered {res.status_code}"
        if res.status_code in (401, 403):
            raise CliError(message, AUTH)
        if res.status_code == 409:
            raise CliError(message, CONFLICT)
        raise CliError(message, GENERAL)

    def get(self, path: str, **params):
        return self.request("GET", path, params={k: v for k, v in params.items() if v is not None})

    def post(self, path: str, body: dict | None = None, **kwargs):
        if body is not None:
            kwargs["json"] = body
        return self.request("POST", path, **kwargs)

    def events(self, path: str, last_id: str | None) -> Iterator[tuple[str | None, str, str]]:
        """Yield (id, event, data) from a live stream until it closes."""
        headers = {"Last-Event-ID": last_id} if last_id else {}
        with self.http.stream(
            "GET", path, headers=headers, timeout=httpx.Timeout(10, read=None)
        ) as res:
            if res.status_code != 200:
                res.read()
                try:
                    message = res.json()["error"]["message"]
                except (ValueError, KeyError, TypeError):
                    message = f"The server answered {res.status_code}"
                raise CliError(message, AUTH if res.status_code in (401, 403) else GENERAL)
            block: list[str] = []
            for line in res.iter_lines():
                if line:
                    block.append(line)
                    continue
                event_id, name, data = None, "message", []
                for item in block:
                    if item.startswith("id: "):
                        event_id = item[4:]
                    elif item.startswith("event: "):
                        name = item[7:]
                    elif item.startswith("data: "):
                        data.append(item[6:])
                block = []
                if data:
                    yield event_id, name, "\n".join(data)


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)
