"""The content gateway: serves published files on their own origin (SDD section 7).

Run it separately from the API, on the address in CONTENT_ORIGIN:
    uvicorn app.content:app --port 8001

It never trusts cookies. A link carries a signed token in the path, so relative links inside
a page (style.css, app.js, images) keep working and it also works inside a frame on another site.
Every response, errors included, carries the security headers.
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.signing import read_content_token
from app.db.models import Page, PageVersion, VersionFile
from app.db.session import get_session
from app.services.storage import get_storage

BRIDGE_PATH = "/_paddock/bridge.js"
MAX_INJECTED_HTML = 8 * 1024 * 1024  # larger pages are served as they are, without the helper


@lru_cache
def bridge_source() -> bytes:
    return Path(__file__).with_name("content_bridge.js").read_bytes()


def with_bridge(html: bytes) -> bytes:
    """Add the helper script to a page, so the app can update parts of it and anchor comments.

    It goes just before the closing body tag (or at the end). The helper does nothing unless the
    page is shown inside the Paddock app, and it only listens to messages from that origin.
    """
    origin = get_settings().app_origin.rstrip("/")
    tag = (
        f'<script src="{BRIDGE_PATH}" data-paddock-bridge data-app-origin="{origin}"></script>'
    ).encode()
    closing = list(re.finditer(rb"</body\s*>", html, re.IGNORECASE))
    if closing:
        at = closing[-1].start()
        return html[:at] + tag + html[at:]
    return html + tag


def security_headers() -> dict[str, str]:
    settings = get_settings()
    return {
        "Content-Security-Policy": (
            "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; "
            f"connect-src 'self'; frame-ancestors {settings.app_origin}; "
            "form-action 'none'; base-uri 'none'"
        ),
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Cross-Origin-Resource-Policy": "same-site",
        "X-Robots-Tag": "noindex, nofollow",
    }


def create_content_app() -> FastAPI:
    app = FastAPI(title="Paddock content", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def add_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in security_headers().items():
            response.headers[name] = value
        return response

    def not_found() -> PlainTextResponse:
        return PlainTextResponse(
            "Not found", status_code=404, headers={"Cache-Control": "no-store"}
        )

    @app.get("/healthz")
    async def healthz():
        # The app asks this from the browser to learn the server is really awake (rather than
        # showing the host's waking-up screen), so it may read the answer.
        return JSONResponse(
            {"status": "ok"},
            headers={
                "Access-Control-Allow-Origin": get_settings().app_origin.rstrip("/"),
                "Cache-Control": "no-store",
            },
        )

    @app.get(BRIDGE_PATH)
    async def bridge():
        return Response(
            bridge_source(),
            media_type="text/javascript",
            headers={"Cache-Control": "public, max-age=300"},
        )

    @app.get("/c/{token}/{path:path}")
    async def serve(token: str, path: str, db: Annotated[AsyncSession, Depends(get_session)]):
        found = read_content_token(token)
        if found is None:
            return PlainTextResponse("This link is invalid or has expired", status_code=403)
        page_id, number = found

        row = await db.execute(
            select(PageVersion.id, PageVersion.entry_path)
            .join(Page, Page.id == PageVersion.page_id)
            .where(Page.id == page_id, Page.deleted_at.is_(None), PageVersion.number == number)
        )
        version = row.first()
        if version is None:
            return not_found()
        wanted = _resolve(path, version.entry_path)
        record = await db.scalar(
            select(VersionFile).where(
                VersionFile.version_id == version.id, VersionFile.path == wanted
            )
        )
        if record is None and path and not path.endswith("/"):
            # A directory request such as "docs" falls back to "docs/index.html".
            record = await db.scalar(
                select(VersionFile).where(
                    VersionFile.version_id == version.id, VersionFile.path == f"{wanted}/index.html"
                )
            )
        if record is None:
            return not_found()

        if (
            record.content_type.split(";")[0].strip().lower() == "text/html"
            and record.size_bytes <= MAX_INJECTED_HTML
        ):
            raw = b"".join([chunk async for chunk in get_storage().open(record.sha256)])
            body = with_bridge(raw)
            return Response(
                body,
                media_type=record.content_type,
                headers={"Cache-Control": "private, max-age=300"},
            )

        return StreamingResponse(
            get_storage().open(record.sha256),
            media_type=record.content_type,
            headers={
                "Content-Length": str(record.size_bytes),
                "Cache-Control": "private, max-age=300",
            },
        )

    return app


def _resolve(path: str, entry: str) -> str:
    """Map a request path to a file path in the bundle."""
    path = path.lower().strip("/")
    if not path:
        return entry
    return path


app = create_content_app()
