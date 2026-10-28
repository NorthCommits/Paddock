import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, comments, events, health, pages, sharing, tokens, webhooks
from app.api import oauth as oauth_api
from app.core import ratelimit
from app.core.config import get_settings
from app.core.errors import error_response, register_error_handlers
from app.db.session import get_engine
from app.services import retention
from app.services import webhooks as webhooks_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    if get_settings().webhook_worker:
        webhooks_service.worker.start()
    cleanup = asyncio.create_task(retention.loop()) if get_settings().retention_enabled else None
    yield
    if cleanup:
        cleanup.cancel()
    await webhooks_service.worker.stop()
    await get_engine().dispose()


SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def early_refusal(request: Request, settings):
    """Turn away oversized bodies and callers who are over their limit before any work is done."""
    declared = request.headers.get("content-length", "")
    biggest = settings.max_bundle_bytes * 2 + 2 * 1024 * 1024
    if declared.isdigit() and int(declared) > biggest:
        return error_response(request, 413, "payload_too_large", "The request body is too large")
    wait = ratelimit.general_wait(request)
    if wait is not None:
        return error_response(
            request, 429, "rate_limited", f"Too many requests. Try again in {wait} seconds.", wait
        )
    return None


OPEN_CORS_PREFIXES = ("/oauth", "/.well-known", "/mcp")


class PathCORS:
    """Agent-facing paths allow any origin without credentials; everything else keeps the
    site-only, credentialed rules."""

    def __init__(self, app, *, app_origin: str):
        self.open = CORSMiddleware(
            app,
            allow_origins=["*"],
            allow_credentials=False,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID", "WWW-Authenticate", "Mcp-Session-Id"],
        )
        self.site = CORSMiddleware(
            app,
            allow_origins=[app_origin],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
            expose_headers=["X-Request-ID"],
        )

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "") if scope["type"] == "http" else ""
        if any(path == p or path.startswith(p + "/") for p in OPEN_CORS_PREFIXES):
            await self.open(scope, receive, send)
        else:
            await self.site(scope, receive, send)


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)

    app = FastAPI(title="Paddock API", version="0.1.0", lifespan=lifespan)

    app.add_middleware(PathCORS, app_origin=settings.app_origin)

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        started = time.perf_counter()
        request.state.request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        response = early_refusal(request, settings)
        if response is None:
            response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if settings.environment == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
        took_ms = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Server-Timing"] = f"app;dur={took_ms:.0f}"
        if took_ms > 1000:
            logging.getLogger("paddock.slow").warning(
                "%s %s took %.0f ms", request.method, request.url.path, took_ms
            )
        return response

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(tokens.router)
    app.include_router(pages.router)
    app.include_router(sharing.router)
    app.include_router(sharing.public)
    app.include_router(comments.router)
    app.include_router(events.router)
    app.include_router(webhooks.router)
    app.include_router(oauth_api.router)
    return app


app = create_app()
