"""Comments, replies and the @agent mention (SDD sections 4.4 and 5.3)."""

import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import (
    ApiToken,
    Comment,
    OAuthClient,
    Page,
    PageVersion,
    RequestOffer,
    RevisionRequest,
    User,
)
from app.schemas.comments import AuthorOut, CommentListOut, CommentOut, RequestOut
from app.services import approvals, audit, events
from app.services.pages import get_for_actor, role_for

# "@agent" as a whole word, in any case. "@agentic" and "name@agent.com" do not count.
MENTION = re.compile(r"(?<![A-Za-z0-9_@])@agent(?![A-Za-z0-9_-])", re.IGNORECASE)


def mentions_agent(body: str) -> bool:
    return MENTION.search(body) is not None


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- output


async def version_numbers(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, int]:
    if not ids:
        return {}
    rows = await db.execute(
        select(PageVersion.id, PageVersion.number).where(PageVersion.id.in_(ids))
    )
    return {row.id: row.number for row in rows}


def request_out(
    r: RevisionRequest,
    numbers: dict[uuid.UUID, int],
    approver: User | None = None,
    asked: int = 0,
    my_offer: str | None = None,
) -> RequestOut:
    return RequestOut(
        id=r.id,
        page_id=r.page_id,
        comment_id=r.comment_id,
        status=r.status,  # type: ignore[arg-type]
        base_version=numbers.get(r.base_version_id) if r.base_version_id else None,
        result_version=numbers.get(r.result_version_id) if r.result_version_id else None,
        claim_expires_at=r.claim_expires_at,
        dismiss_reason=r.dismiss_reason,
        created_at=r.created_at,
        updated_at=r.updated_at,
        approved_by=(approver.display_name or f"@{approver.handle}") if approver else None,
        asked=asked,
        my_offer=my_offer,
        brief=r.brief,
    )


def author_out(
    comment: Comment, users: dict[uuid.UUID, User], labels: dict[uuid.UUID, str] | None = None
) -> AuthorOut:
    user = users.get(comment.author_user_id) if comment.author_user_id else None
    return AuthorOut(
        user_id=user.id if user else None,
        handle=user.handle if user else None,
        display_name=user.display_name if user else None,
        by_agent=comment.author_token_id is not None,
        agent_label=(labels or {}).get(comment.id),
    )


SIGN_IN_SUFFIX = " (connected with sign-in)"


async def agent_labels(
    db: AsyncSession, comments: list[Comment], users: dict[uuid.UUID, User]
) -> dict[uuid.UUID, str]:
    """A name for each comment an agent wrote, such as "Swapnil's Claude" (owner, then app)."""
    token_ids = {c.author_token_id for c in comments if c.author_token_id}
    if not token_ids:
        return {}
    tokens = {t.id: t for t in await db.scalars(select(ApiToken).where(ApiToken.id.in_(token_ids)))}
    client_ids = {t.client_id for t in tokens.values() if t.client_id}
    clients: dict[str, str] = {}
    if client_ids:
        rows = await db.scalars(select(OAuthClient).where(OAuthClient.client_id.in_(client_ids)))
        clients = {c.client_id: c.client_name for c in rows}
    out: dict[uuid.UUID, str] = {}
    for c in comments:
        token = tokens.get(c.author_token_id) if c.author_token_id else None
        if token is None:
            continue
        app = clients.get(token.client_id or "") or token.name.removesuffix(SIGN_IN_SUFFIX)
        owner = users.get(c.author_user_id) if c.author_user_id else None
        first = ((owner.display_name or "").split() or [owner.handle])[0] if owner else ""
        out[c.id] = f"{first}'s {app}" if first else app
    return out


async def users_by_id(db: AsyncSession, ids: set[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not ids:
        return {}
    return {u.id: u for u in await db.scalars(select(User).where(User.id.in_(ids)))}


async def comment_outs(
    db: AsyncSession, comments: list[Comment], viewer_id: uuid.UUID | None = None
) -> dict[uuid.UUID, CommentOut]:
    """Flat output for each comment, keyed by id. Replies are attached by the caller.

    viewer_id is the person looking, so a request can say whether they may say yes to it.
    """
    ids = {c.id for c in comments}
    users = await users_by_id(
        db,
        {c.author_user_id for c in comments if c.author_user_id}
        | {c.resolved_by for c in comments if c.resolved_by},
    )
    requests = {}
    if ids:
        requests = {
            r.comment_id: r
            for r in await db.scalars(
                select(RevisionRequest).where(RevisionRequest.comment_id.in_(ids))
            )
        }
    version_ids = {c.version_id for c in comments if c.version_id}
    for r in requests.values():
        version_ids |= {v for v in (r.base_version_id, r.result_version_id) if v}
    numbers = await version_numbers(db, version_ids)
    labels = await agent_labels(db, comments, users)
    approvers = await users_by_id(
        db, {r.approved_by_user_id for r in requests.values() if r.approved_by_user_id}
    )
    asked: dict[uuid.UUID, int] = {}
    mine: dict[uuid.UUID, str] = {}
    if requests:
        for offer in await db.scalars(
            select(RequestOffer).where(
                RequestOffer.request_id.in_([r.id for r in requests.values()])
            )
        ):
            asked[offer.request_id] = asked.get(offer.request_id, 0) + 1
            if offer.user_id == viewer_id:
                mine[offer.request_id] = offer.status

    out: dict[uuid.UUID, CommentOut] = {}
    for c in comments:
        gone = c.deleted_at is not None
        request = requests.get(c.id)
        out[c.id] = CommentOut(
            id=c.id,
            page_id=c.page_id,
            parent_id=c.parent_id,
            version_number=numbers.get(c.version_id) if c.version_id else None,
            author=AuthorOut(user_id=None, handle=None, display_name=None, by_agent=False)
            if gone
            else author_out(c, users, labels),
            body="" if gone else c.body,
            anchor=None if gone else c.anchor,
            mentions_agent=False if gone else c.mentions_agent,
            created_at=c.created_at,
            edited_at=c.edited_at,
            deleted=gone,
            resolved_at=c.resolved_at,
            resolved_by=users[c.resolved_by].handle if c.resolved_by in users else None,
            request=request_out(
                request,
                numbers,
                approvers.get(request.approved_by_user_id) if request.approved_by_user_id else None,
                asked.get(request.id, 0),
                mine.get(request.id),
            )
            if request and not gone
            else None,
        )
    return out


# ---------------------------------------------------------------- helpers


async def _version_id(db: AsyncSession, page: Page, number: int | None) -> uuid.UUID | None:
    if number is None:
        return page.current_version_id
    found = await db.scalar(
        select(PageVersion.id).where(PageVersion.page_id == page.id, PageVersion.number == number)
    )
    if found is None:
        raise AppError(422, "validation_failed", "That version does not exist on this page")
    return found


async def _comment_for(
    db: AsyncSession, actor, comment_id: uuid.UUID, action: str
) -> tuple[Comment, Page]:
    comment = await db.get(Comment, comment_id)
    if comment is None or comment.deleted_at is not None:
        raise AppError(404, "not_found", "Comment not found")
    page = await get_for_actor(db, actor, comment.page_id, action)
    return comment, page


def _request_for(db: AsyncSession, comment_id: uuid.UUID):
    return db.scalar(select(RevisionRequest).where(RevisionRequest.comment_id == comment_id))


def _token_id(actor) -> uuid.UUID | None:
    return actor.token.id if actor.token else None


# ---------------------------------------------------------------- operations


async def request_event(
    db: AsyncSession, page: Page, request: RevisionRequest, type_: str, comment: Comment
):
    """Tell streams and webhooks about a request, with enough to act on it."""
    await events.emit(
        db,
        page.id,
        type_,
        {
            "request_id": str(request.id),
            "comment_id": str(comment.id),
            "thread_id": str(comment.parent_id or comment.id),
            "body": comment.body,
            "base_version": await _number(db, request.base_version_id),
        },
    )


async def _number(db: AsyncSession, version_id: uuid.UUID | None) -> int | None:
    if version_id is None:
        return None
    return (await version_numbers(db, {version_id})).get(version_id)


async def comment_created(
    db: AsyncSession, page: Page, comment: Comment, request: RevisionRequest | None, by_agent: bool
) -> None:
    await events.emit(
        db,
        page.id,
        "comment.created",
        {
            "comment_id": str(comment.id),
            "thread_id": str(comment.parent_id or comment.id),
            "body": comment.body,
            "by_agent": by_agent,
            "mentions_agent": comment.mentions_agent,
            "request_id": str(request.id) if request else None,
        },
    )
    if request is not None:
        await request_event(db, page, request, "request.created", comment)


async def create(
    db: AsyncSession,
    actor,
    page_id: uuid.UUID,
    *,
    body: str,
    parent_id: uuid.UUID | None,
    version: int | None,
    anchor: dict | None,
    ip: str | None,
    brief: str | None = None,
) -> CommentOut:
    page = await get_for_actor(db, actor, page_id, "comment.create")
    parent = None
    if parent_id is not None:
        parent = await db.get(Comment, parent_id)
        if parent is None or parent.page_id != page.id or parent.deleted_at is not None:
            raise AppError(404, "not_found", "Comment not found")
        if parent.parent_id is not None:  # a reply to a reply joins the same thread
            parent = await db.get(Comment, parent.parent_id)

    comment = Comment(
        page_id=page.id,
        version_id=await _version_id(db, page, version),
        parent_id=parent.id if parent else None,
        author_user_id=actor.user.id,
        author_token_id=_token_id(actor),
        body=body,
        anchor=None if parent else anchor,
        mentions_agent=mentions_agent(body),
    )
    db.add(comment)
    await db.flush()
    # Only people ask agents for work. An agent mentioning @agent in its own text does not
    # start another request, so agents cannot trigger each other in a loop.
    request = None
    if comment.mentions_agent and actor.is_person:
        request = RevisionRequest(
            page_id=page.id,
            comment_id=comment.id,
            requested_by=actor.user.id,
            base_version_id=page.current_version_id,
            brief=(brief or "").strip() or None,
        )
        db.add(request)
        await db.flush()
        routed = await approvals.route(db, page, comment, request, actor.user)
    elif parent is not None and actor.is_person:
        # A person answering in the thread of a request that is waiting for information.
        asked = await _request_for(db, parent.id)
        if asked is not None and asked.status == "needs_info":
            asked.status = "open"
            await events.emit(db, page.id, "request.answered", {"request_id": str(asked.id)})
    await comment_created(db, page, comment, request, actor.token is not None)
    audit.record(
        db,
        action="comment.create",
        user_id=actor.user.id,
        token_id=_token_id(actor),
        target_type="comment",
        target_id=str(comment.id),
        ip=ip,
        meta={"page_id": str(page.id), "mention": comment.mentions_agent},
    )
    await db.commit()
    await db.refresh(comment)
    if request is not None:
        await approvals.after_commit(db, page, comment, request, actor.user, routed)
    return (await comment_outs(db, [comment], actor.user.id))[comment.id]


async def list_for_page(
    db: AsyncSession, actor, page_id: uuid.UUID, status: str | None
) -> CommentListOut:
    page = await get_for_actor(db, actor, page_id, "comment.read")
    rows = list(
        await db.scalars(
            select(Comment)
            .where(Comment.page_id == page.id)
            .order_by(Comment.created_at, Comment.id)
        )
    )
    # A deleted first comment stays as a placeholder while it still has replies.
    has_replies = {c.parent_id for c in rows if c.parent_id and c.deleted_at is None}
    shown = [c for c in rows if c.deleted_at is None or c.id in has_replies]
    outs = await comment_outs(db, shown, actor.user.id)
    threads: list[CommentOut] = []
    for c in shown:
        if c.parent_id is None:
            threads.append(outs[c.id])
        elif c.parent_id in outs:
            outs[c.parent_id].replies.append(outs[c.id])
    if status == "open":
        threads = [t for t in threads if t.resolved_at is None]
    elif status == "resolved":
        threads = [t for t in threads if t.resolved_at is not None]
    return CommentListOut(items=threads)


async def edit(
    db: AsyncSession, actor, comment_id: uuid.UUID, *, body: str, ip: str | None
) -> CommentOut:
    comment, page = await _comment_for(db, actor, comment_id, "comment.create")
    if comment.author_user_id != actor.user.id:
        raise AppError(403, "forbidden", "You can only edit your own comments")
    if body != comment.body:
        comment.body = body
        comment.edited_at = _now()
        wants = mentions_agent(body)
        request = await _request_for(db, comment.id)
        routed = None
        if wants and request is None and comment.author_token_id is None:
            request = RevisionRequest(
                page_id=page.id,
                comment_id=comment.id,
                requested_by=actor.user.id,
                base_version_id=page.current_version_id,
            )
            db.add(request)
            await db.flush()
            routed = await approvals.route(db, page, comment, request, actor.user)
            await request_event(db, page, request, "request.created", comment)
        elif wants and request is not None and request.status == "dismissed":
            # The mention is back, so the request is too, and it is routed afresh.
            request.base_version_id = page.current_version_id
            request.dismiss_reason = None
            request.claimed_by_token_id = None
            request.claim_expires_at = None
            await approvals.reset(db, request)
            routed = await approvals.route(db, page, comment, request, actor.user)
            await request_event(db, page, request, "request.created", comment)
        elif not wants and request is not None and request.status in ("open", "awaiting"):
            request.status = "dismissed"
            request.dismiss_reason = "The mention was removed"
            await events.emit(
                db,
                page.id,
                "request.dismissed",
                {"request_id": str(request.id), "reason": request.dismiss_reason},
            )
        comment.mentions_agent = wants
        await events.emit(
            db, page.id, "comment.updated", {"comment_id": str(comment.id), "body": body}
        )
        audit.record(
            db,
            action="comment.update",
            user_id=actor.user.id,
            token_id=_token_id(actor),
            target_type="comment",
            target_id=str(comment.id),
            ip=ip,
        )
        await db.commit()
        await db.refresh(comment)
        if routed is not None and request is not None:
            await approvals.after_commit(db, page, comment, request, actor.user, routed)
    return (await comment_outs(db, [comment], actor.user.id))[comment.id]


async def delete(db: AsyncSession, actor, comment_id: uuid.UUID, *, ip: str | None) -> None:
    comment, page = await _comment_for(db, actor, comment_id, "comment.create")
    role = await role_for(db, page, actor.user)
    if comment.author_user_id != actor.user.id and role not in ("owner", "editor"):
        raise AppError(403, "forbidden", "Only the author, an editor or the owner can delete this")
    comment.deleted_at = _now()
    request = await _request_for(db, comment.id)
    if request is not None and request.status in ("awaiting", "open", "claimed", "needs_info"):
        request.status = "dismissed"
        request.dismiss_reason = "The comment was deleted"
        request.claimed_by_token_id = None
        request.claim_expires_at = None
        await events.emit(
            db,
            page.id,
            "request.dismissed",
            {"request_id": str(request.id), "reason": request.dismiss_reason},
        )
    await events.emit(db, page.id, "comment.deleted", {"comment_id": str(comment.id)})
    audit.record(
        db,
        action="comment.delete",
        user_id=actor.user.id,
        token_id=_token_id(actor),
        target_type="comment",
        target_id=str(comment.id),
        ip=ip,
    )
    await db.commit()


async def resolve(
    db: AsyncSession, actor, comment_id: uuid.UUID, *, resolved: bool, ip: str | None
) -> CommentOut:
    comment, page = await _comment_for(db, actor, comment_id, "comment.create")
    if comment.parent_id is not None:
        raise AppError(422, "validation_failed", "Resolve the first comment of the thread")
    comment.resolved_at = _now() if resolved else None
    comment.resolved_by = actor.user.id if resolved else None
    await events.emit(
        db, page.id, "comment.resolved", {"comment_id": str(comment.id), "resolved": resolved}
    )
    audit.record(
        db,
        action="comment.resolve" if resolved else "comment.reopen",
        user_id=actor.user.id,
        token_id=_token_id(actor),
        target_type="comment",
        target_id=str(comment.id),
        ip=ip,
    )
    await db.commit()
    await db.refresh(comment)
    return (await comment_outs(db, [comment]))[comment.id]
