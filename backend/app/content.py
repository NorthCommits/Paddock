"""The content gateway: serves published files on their own origin (SDD section 7).

Run it separately from the API, on the address in CONTENT_ORIGIN:
    uvicorn app.content:app --port 8001

It never trusts cookies. A link carries a signed token in the path, so relative links inside
a page (style.css, app.js, images) keep working and it also works inside a frame on another site.
Every response, errors included, carries the security headers.
"""

from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.signing import read_content_token
from app.db.models import Page, PageVersion, VersionFile
from app.db.session import get_session
from app.services.storage import get_storage


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
        return {"status": "ok"}

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
