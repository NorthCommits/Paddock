"""The eight Paddock tools. Each is a thin wrapper over the same services the REST routes use,
so roles, scopes, limits, rate limits and audit records are the same however an agent connects.

The docstrings are what the agent reads to decide when and how to call a tool.
"""

import base64
import uuid
from contextlib import asynccontextmanager
from typing import Any, Literal

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field, ValidationError
from starlette.requests import Request

from app.api.bundle_input import decode_file
from app.api.deps import Actor, get_verified_actor
from app.core import ratelimit
from app.core.config import get_settings
from app.core.errors import AppError
from app.db.session import get_sessionmaker
from app.schemas.comments import ClaimIn, CommentIn, CompleteIn
from app.schemas.pages import PageFields, VersionFields
from app.services import comments, pages, requests, tokens
from app.services.bundles import TEXT_EXTENSIONS, check_bundle, extension
from app.services.storage import get_storage

# get_page stops inlining file contents after this many bytes, so one call cannot flood the
# agent's context. Files past the budget are listed without content.
CONTENT_BUDGET = 2 * 1024 * 1024


class PageFile(BaseModel):
    path: str = Field(
        description="Path inside the page, for example 'index.html' or 'assets/logo.png'. "
        "Lowercase letters, digits, dots, dashes, underscores and slashes only."
    )
    content: str = Field(description="The file content: plain text, or base64 for binary files.")
    encoding: Literal["utf-8", "base64"] = Field(
        default="utf-8", description="'utf-8' for text files, 'base64' for images and fonts."
    )


# ------------------------------------------------------------------ helpers


def _request(ctx: Context | None) -> Request | None:
    try:
        request = ctx.request_context.request if ctx else None
    except ValueError:
        return None
    return request if isinstance(request, Request) else None


def _need(actor: Actor, scope: str) -> None:
    if scope not in actor.scopes:
        raise AppError(403, "forbidden", f"This token lacks the {scope} scope")


def _id(value: str, name: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        raise ToolError(
            f"{name} must be a Paddock id like 3f2b8c1e-... (copy it from an earlier result)"
        ) from None


def _check[T: BaseModel](model: type[T], **fields: Any) -> T:
    try:
        return model.model_validate(fields)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        raise AppError(422, "validation_failed", f"{where}: {first['msg']}") from None


def _page_url(page_id: uuid.UUID | str) -> str:
    return f"{get_settings().app_origin.rstrip('/')}/pages/{page_id}"


@asynccontextmanager
async def acting_user(ctx: Context | None = None, *, write: bool = False, rule: str | None = None):
    """Who is calling, as the same Actor the REST routes build from an agent token.

    Opens a fresh database session for this one call. With write=True the person behind the
    token must have a verified email, like publishing over REST. rule applies a named rate
    limit. Any AppError inside becomes a tool error that carries its message.
    """
    access = get_access_token()
    if access is None:
        raise ToolError("Not signed in to Paddock. Reconnect and sign in again.")
    request = _request(ctx)
    try:
        if rule and request is not None:
            ratelimit.limit(rule)(request)
        async with get_sessionmaker()() as db:
            found = await tokens.find(db, access.token)
            if found is None:
                raise ToolError("This Paddock connection was revoked. Reconnect to continue.")
            user, token = found
            actor = Actor(user=user, scopes=frozenset(token.scopes), token=token)
            if write:
                await get_verified_actor(actor)
            yield db, actor
    except AppError as exc:
        raise ToolError(exc.message) from None


def _ip(ctx: Context | None) -> str | None:
    request = _request(ctx)
    return ratelimit.caller_ip(request) if request is not None else None


def _page_summary(out) -> dict:
    current = out.current_version
    return {
        "id": str(out.id),
        "title": out.title,
        "slug": out.slug,
        "owner_handle": out.owner_handle,
        "your_role": out.role,
        "visibility": out.visibility,
        "version": current.number if current else None,
        "updated_at": out.updated_at.isoformat(),
        "url": _page_url(out.id),
    }


async def _read(sha256: str) -> bytes:
    return b"".join([chunk async for chunk in get_storage().open(sha256)])


# ------------------------------------------------------------------ pages


async def list_pages(limit: int = 20, ctx: Context | None = None) -> dict:
    """List the Paddock pages you can open: the person's own pages and pages shared with them.

    Use this to find a page's id before get_page, publish_page (to add a version) or
    list_comments. Newest changes come first.

    Args:
        limit: How many pages to return, 1 to 100. Default 20.

    Returns {"pages": [{id, title, slug, owner_handle, your_role, visibility, version,
    updated_at, url}], "more": true when there are more pages than returned}.
    """
    async with acting_user(ctx) as (db, actor):
        _need(actor, "pages:read")
        rows, next_cursor = await pages.list_pages(
            db, actor, limit=max(1, min(limit, 100)), cursor=None, slug=None
        )
        outs = await pages.page_outs(db, rows, actor.user)
        return {"pages": [_page_summary(o) for o in outs], "more": next_cursor is not None}


async def get_page(page_id: str, ctx: Context | None = None) -> dict:
    """Read one page: its details and the files of its latest version.

    Call this before changing a page so you edit what is really there. Text files (html, css,
    js, json, svg, txt) come back as text with encoding "utf-8"; images, fonts and video come
    back base64 encoded with encoding "base64". Very large pages list the later files without
    content.

    Args:
        page_id: The page id from list_pages or publish_page.

    Returns {id, title, slug, url, your_role, version, entry_path, files: [{path,
    content_type, encoding, content}]}.
    """
    pid = _id(page_id, "page_id")
    async with acting_user(ctx) as (db, actor):
        page = await pages.get_for_actor(db, actor, pid, "page.view")
        out = await pages.page_out(db, page, actor.user)
        result = {**_page_summary(out), "entry_path": None, "files": []}
        if out.current_version is None:
            return result
        detail = await pages.version_detail(
            db, await pages.get_version(db, page, out.current_version.number)
        )
        result["entry_path"] = detail.entry_path
        budget = CONTENT_BUDGET
        for f in detail.files:
            item: dict[str, Any] = {"path": f.path, "content_type": f.content_type}
            if f.size_bytes > budget:
                item.update(encoding=None, content=None, omitted="too large to include here")
            else:
                data = await _read(f.sha256)
                budget -= len(data)
                if extension(f.path) in TEXT_EXTENSIONS:
                    item.update(encoding="utf-8", content=data.decode("utf-8", "replace"))
                else:
                    item.update(encoding="base64", content=base64.b64encode(data).decode())
            result["files"].append(item)
        return result


async def publish_page(
    title: str,
    files: list[PageFile],
    page_id: str | None = None,
    message: str | None = None,
    entry_path: str | None = None,
    ctx: Context | None = None,
) -> dict:
    """Publish a web page on Paddock, or a new version of an existing page.

    Without page_id this creates a new page. With page_id it adds a version to that page and
    keeps the old versions; title is then ignored. Always send the complete set of files for
    the version, not only the changed ones. Sending the same files again changes nothing.

    Args:
        title: The page title people see, up to 200 characters.
        files: Every file of the page, each {"path", "content", "encoding"}. Include an
            index.html (or set entry_path). Text files use encoding "utf-8" (the default);
            images and fonts use encoding "base64" with the bytes base64 encoded.
            Example: [{"path": "index.html", "content": "<h1>Hi</h1>"},
            {"path": "logo.png", "content": "iVBORw0...", "encoding": "base64"}].
        page_id: The page to update. Leave empty to create a new page.
        message: A short note on what changed, shown in the version history.
        entry_path: The HTML file that opens first. Default "index.html".

    Returns {page_id, title, version, created, url}. created is false when the files were
    identical to the current version. Give the url to the person so they can open the page.
    """
    pid = _id(page_id, "page_id") if page_id else None
    async with acting_user(ctx, write=True, rule="publish") as (db, actor):
        _need(actor, "pages:write")
        if pid is None:
            fields = _check(PageFields, title=title, message=message, entry_path=entry_path)
        else:
            fields = _check(VersionFields, message=message, entry_path=entry_path)
        incoming = [decode_file(f.path, f.content, f.encoding) for f in files]
        checked, entry = check_bundle(incoming, fields.entry_path, get_settings())
        if pid is None:
            page, version = await pages.create(
                db,
                actor,
                title=fields.title,
                slug=None,
                message=fields.message,
                files=checked,
                entry_path=entry,
                ip=_ip(ctx),
            )
            created = True
        else:
            page, version, created = await pages.publish(
                db,
                actor,
                pid,
                files=checked,
                entry_path=entry,
                message=fields.message,
                base_version=None,
                ip=_ip(ctx),
            )
        return {
            "page_id": str(page.id),
            "title": page.title,
            "version": version.number,
            "created": created,
            "url": _page_url(page.id),
        }


# ------------------------------------------------------------------ comments


async def list_comments(
    page_id: str, status: str | None = None, ctx: Context | None = None
) -> dict:
    """List the comment threads on a page, oldest first, each with its replies.

    Use this to see what people said about a page. A thread that asks for work from you
    contains @agent and carries a request; act on those with list_requests and claim_request.

    Args:
        page_id: The page id.
        status: "open" for unresolved threads, "resolved" for resolved ones, or empty for all.

    Returns {"comments": [{id, body, author, version_number, anchor, resolved_at, request,
    replies: [...]}]}. Use a thread's id as comment_id in reply_to_comment.
    """
    pid = _id(page_id, "page_id")
    if status not in (None, "open", "resolved"):
        raise ToolError("status must be 'open', 'resolved', or left empty")
    async with acting_user(ctx) as (db, actor):
        out = await comments.list_for_page(db, actor, pid, status)
        return {"comments": [c.model_dump(mode="json") for c in out.items]}


async def reply_to_comment(
    page_id: str, comment_id: str, body: str, ctx: Context | None = None
) -> dict:
    """Reply in a comment thread on a page, for example to answer a question or say what you
    changed.

    Args:
        page_id: The page id.
        comment_id: The id of any comment in the thread (from list_comments).
        body: Your reply, plain text, up to 5000 characters.

    Returns the new comment {id, parent_id, body, ...}.
    """
    pid = _id(page_id, "page_id")
    cid = _id(comment_id, "comment_id")
    async with acting_user(ctx, write=True, rule="comment") as (db, actor):
        _need(actor, "comments:write")
        fields = _check(CommentIn, body=body, parent_id=cid)
        out = await comments.create(
            db,
            actor,
            pid,
            body=fields.body,
            parent_id=fields.parent_id,
            version=None,
            anchor=None,
            ip=_ip(ctx),
        )
        return out.model_dump(mode="json")


# ------------------------------------------------------------------ requests


async def list_requests(status: str | None = "open", ctx: Context | None = None) -> dict:
    """List revision requests: changes people asked you for by writing @agent in a comment.

    Work through them oldest first: claim_request, publish the fix with publish_page, then
    complete_request with the new version number.

    Args:
        status: "open" (default, waiting for an agent), "claimed", "done", "dismissed", or
            empty for all.

    Returns {"requests": [{id, status, page_id, page_title, comment: {body, ...},
    base_version, ...}]}.
    """
    if status not in (None, "open", "claimed", "done", "dismissed"):
        raise ToolError("status must be 'open', 'claimed', 'done', 'dismissed', or left empty")
    async with acting_user(ctx) as (db, actor):
        out = await requests.list_requests(db, actor, status=status, page_id=None, limit=50)
        return {"requests": [r.model_dump(mode="json") for r in out.items]}


async def claim_request(request_id: str, minutes: int = 10, ctx: Context | None = None) -> dict:
    """Claim a revision request before working on it, so no other agent picks it up.

    The claim lasts the given minutes; claim again to extend it. If it runs out the request
    opens again for others.

    Args:
        request_id: The request id from list_requests.
        minutes: How long to hold the claim, 1 to 60. Default 10.

    Returns the request with status "claimed".
    """
    rid = _id(request_id, "request_id")
    async with acting_user(ctx, write=True, rule="request") as (db, actor):
        _need(actor, "requests:act")
        fields = _check(ClaimIn, minutes=minutes)
        out = await requests.claim(db, actor, rid, minutes=fields.minutes, ip=_ip(ctx))
        return out.model_dump(mode="json")


async def complete_request(
    request_id: str, result_version: int, reply: str | None = None, ctx: Context | None = None
) -> dict:
    """Finish a revision request you claimed, after publishing the fix with publish_page.

    Args:
        request_id: The request id.
        result_version: The version number publish_page returned for the fix. It must be
            published after the request was made.
        reply: A short note for the person about what you changed, posted in the thread.
            Default "Published version N."

    Returns the request with status "done".
    """
    rid = _id(request_id, "request_id")
    async with acting_user(ctx, write=True, rule="request") as (db, actor):
        _need(actor, "requests:act")
        fields = _check(CompleteIn, result_version=result_version, reply=reply)
        out = await requests.complete(
            db,
            actor,
            rid,
            result_version=fields.result_version,
            reply=fields.reply,
            ip=_ip(ctx),
        )
        return out.model_dump(mode="json")


READ = ToolAnnotations(read_only_hint=True, open_world_hint=False)
WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)

TOOLS = [
    (list_pages, READ),
    (get_page, READ),
    (publish_page, WRITE),
    (list_comments, READ),
    (reply_to_comment, WRITE),
    (list_requests, READ),
    (claim_request, WRITE),
    (complete_request, WRITE),
]
