"""Revision requests: what an @agent mention asks an agent to do (SDD section 5.4).

awaiting --a person says yes--> open --claim--> claimed --complete--> done
claimed --agent asks--> needs_info --person answers or edits the brief--> open
awaiting, open, claimed or needs_info --dismiss--> dismissed
A request starts out awaiting when it needs someone's yes (see approvals.py), or open when the
person who asked uses their own agent. Only the person who said yes has their agent offered the
request. A claim that runs out goes back to open, and a yes that nobody's agent acts on within half
an hour is asked for again. This happens whenever requests are read or claimed,
so it does not depend on a background job staying awake.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models import (
    Comment,
    Page,
    PageMember,
    PageVersion,
    RequestOffer,
    RevisionRequest,
    User,
)
from app.schemas.comments import RequestComment, RequestItemOut, RequestListOut
from app.services import agents, approvals, audit, events, notifications
from app.services import pages as pages_service
from app.services.comments import (
    author_out,
    comment_created,
    request_out,
    users_by_id,
    version_numbers,
)
from app.services.pages import get_for_actor

STALE_YES = timedelta(minutes=30)  # a yes whose agent never started is asked for again


def _now() -> datetime:
    return datetime.now(UTC)


async def reopen_expired(db: AsyncSession) -> None:
    """Return claims that ran out to open. The caller commits."""
    result = await db.execute(
        update(RevisionRequest)
        .where(RevisionRequest.status == "claimed", RevisionRequest.claim_expires_at < _now())
        .values(status="open", claimed_by_token_id=None, claim_expires_at=None)
        .returning(RevisionRequest.id, RevisionRequest.page_id)
    )
    for request_id, page_id in result.all():
        await events.emit(db, page_id, "request.reopened", {"request_id": str(request_id)})
    await _ask_again(db)


async def _ask_again(db: AsyncSession) -> None:
    """A yes that was given in answer to a question, and that no agent has acted on, is asked again.

    A person's own request for their own agent is never asked again, and neither is a standing
    "auto" yes. Only a yes that won against other people's offers can run out.
    """
    stale = await db.scalars(
        select(RevisionRequest)
        .join(
            RequestOffer,
            and_(
                RequestOffer.request_id == RevisionRequest.id,
                RequestOffer.user_id == RevisionRequest.approved_by_user_id,
                RequestOffer.status == "won",
            ),
        )
        .where(
            RevisionRequest.status == "open",
            RevisionRequest.claimed_by_token_id.is_(None),
            RevisionRequest.approved_at < _now() - STALE_YES,
        )
        .with_for_update(of=RevisionRequest, skip_locked=True)
    )
    for request in stale:
        await approvals.release(db, request)


async def _items(db: AsyncSession, rows: list[RevisionRequest]) -> list[RequestItemOut]:
    if not rows:
        return []
    comments = {
        c.id: c
        for c in await db.scalars(
            select(Comment).where(Comment.id.in_([r.comment_id for r in rows]))
        )
    }
    pages = {
        p.id: p
        for p in await db.scalars(select(Page).where(Page.id.in_({r.page_id for r in rows})))
    }
    thread_ids = {c.parent_id or c.id for c in comments.values()}
    threads: dict[uuid.UUID, list[Comment]] = {t: [] for t in thread_ids}
    for c in await db.scalars(
        select(Comment)
        .where(
            or_(Comment.id.in_(thread_ids), Comment.parent_id.in_(thread_ids)),
            Comment.deleted_at.is_(None),
        )
        .order_by(Comment.created_at, Comment.id)
    ):
        threads[c.parent_id or c.id].append(c)
    users = await users_by_id(
        db,
        {c.author_user_id for c in comments.values() if c.author_user_id}
        | {c.author_user_id for t in threads.values() for c in t if c.author_user_id}
        | {p.owner_id for p in pages.values()},
    )
    version_ids = {c.version_id for c in comments.values() if c.version_id}
    version_ids |= {c.version_id for t in threads.values() for c in t if c.version_id}
    for r in rows:
        version_ids |= {v for v in (r.base_version_id, r.result_version_id) if v}
    numbers = await version_numbers(db, version_ids)

    items = []
    for r in rows:
        c, p = comments[r.comment_id], pages[r.page_id]
        items.append(
            RequestItemOut(
                **request_out(r, numbers).model_dump(),
                page_title=p.title,
                page_slug=p.slug,
                owner_handle=users[p.owner_id].handle if p.owner_id in users else "",
                comment=RequestComment(
                    id=c.id,
                    thread_id=c.parent_id or c.id,
                    body=c.body,
                    author=author_out(c, users),
                    version_number=numbers.get(c.version_id) if c.version_id else None,
                    anchor=c.anchor,
                ),
                page_context=p.context_note,
                thread=[
                    RequestComment(
                        id=t.id,
                        thread_id=t.parent_id or t.id,
                        body=t.body,
                        author=author_out(t, users),
                        version_number=numbers.get(t.version_id) if t.version_id else None,
                        anchor=t.anchor,
                    )
                    for t in threads[c.parent_id or c.id]
                ],
            )
        )
    return items


async def list_requests(
    db: AsyncSession, actor, *, status: str | None, page_id: uuid.UUID | None, limit: int
) -> RequestListOut:
    if not actor.scopes & {"comments:read", "requests:act"}:
        raise AppError(403, "forbidden", "This needs the comments:read or requests:act scope")
    await reopen_expired(db)
    await db.commit()
    shared_with_me = select(PageMember.page_id).where(PageMember.user_id == actor.user.id)
    query = (
        select(RevisionRequest)
        .join(Page, Page.id == RevisionRequest.page_id)
        .where(
            Page.deleted_at.is_(None),
            or_(
                Page.owner_id == actor.user.id,
                and_(Page.visibility != "private", Page.id.in_(shared_with_me)),
            ),
        )
    )
    if actor.token is not None:
        # An agent only ever sees what its owner said yes to.
        query = query.where(RevisionRequest.approved_by_user_id == actor.user.id)
    if status:
        query = query.where(RevisionRequest.status == status)
    if page_id:
        query = query.where(RevisionRequest.page_id == page_id)
    # Oldest first, so an agent works through them like a queue.
    rows = list(
        await db.scalars(
            query.order_by(RevisionRequest.created_at, RevisionRequest.id).limit(limit)
        )
    )
    return RequestListOut(items=await _items(db, rows))


async def get_one(db: AsyncSession, actor, request_id: uuid.UUID) -> RequestItemOut:
    if not actor.scopes & {"comments:read", "requests:act"}:
        raise AppError(403, "forbidden", "This needs the comments:read or requests:act scope")
    await reopen_expired(db)
    await db.commit()
    request = await db.get(RevisionRequest, request_id)
    if request is None:
        raise AppError(404, "not_found", "Request not found")
    await _page_for(db, actor, request, "comment.read")
    if actor.token is not None and request.approved_by_user_id != actor.user.id:
        raise AppError(404, "not_found", "Request not found")
    return (await _items(db, [request]))[0]


async def _page_for(db: AsyncSession, actor, request: RevisionRequest, action: str) -> None:
    """Check access to the request's page. Someone who cannot see the page hears only that the
    request was not found, so a request id never reveals that it exists."""
    try:
        await get_for_actor(db, actor, request.page_id, action)
    except AppError as exc:
        if exc.status == 404:
            raise AppError(404, "not_found", "Request not found") from None
        raise


async def _load(db: AsyncSession, actor, request_id: uuid.UUID) -> RevisionRequest:
    """Load a request for update and check the person may act on its page."""
    request = await db.scalar(
        select(RevisionRequest).where(RevisionRequest.id == request_id).with_for_update()
    )
    if request is None:
        raise AppError(404, "not_found", "Request not found")
    await _page_for(db, actor, request, "request.act")
    if (
        request.status == "claimed"
        and request.claim_expires_at
        and request.claim_expires_at <= _now()
    ):
        request.status = "open"
        request.claimed_by_token_id = None
        request.claim_expires_at = None
        await events.emit(db, request.page_id, "request.reopened", {"request_id": str(request.id)})
    return request


def _need_agent(actor) -> None:
    if actor.token is None:
        raise AppError(403, "forbidden", "Requests are picked up by an agent token")


async def _one(db: AsyncSession, request: RevisionRequest) -> RequestItemOut:
    await db.refresh(request)
    return (await _items(db, [request]))[0]


async def claim(db: AsyncSession, actor, request_id: uuid.UUID, *, minutes: int, ip: str | None):
    _need_agent(actor)
    request = await _load(db, actor, request_id)
    if request.status in ("done", "dismissed"):
        raise AppError(409, "conflict", f"This request is already {request.status}")
    if request.status == "awaiting":
        raise AppError(
            409, "awaiting_approval", "A person has not said yes to this request yet, so leave it"
        )
    if request.status == "needs_info":
        raise AppError(
            409, "conflict", "This request is waiting for the person to answer a question"
        )
    if request.approved_by_user_id != actor.user.id:
        raise AppError(403, "forbidden", "This request was approved for someone else's agent")
    if request.status == "claimed" and request.claimed_by_token_id != actor.token.id:
        raise AppError(409, "conflict", "Another agent has claimed this request")
    request.status = "claimed"
    request.claimed_by_token_id = actor.token.id
    request.claim_expires_at = _now() + timedelta(minutes=minutes)
    await events.emit(
        db,
        request.page_id,
        "request.claimed",
        {"request_id": str(request.id), "expires_at": request.claim_expires_at.isoformat()},
    )
    audit.record(
        db,
        action="request.claim",
        user_id=actor.user.id,
        token_id=actor.token.id,
        target_type="request",
        target_id=str(request.id),
        ip=ip,
    )
    await db.commit()
    return await _one(db, request)


async def _reply(
    db: AsyncSession, actor, request: RevisionRequest, comment: Comment, body: str, version_id
) -> None:
    reply = Comment(
        page_id=request.page_id,
        version_id=version_id,
        parent_id=comment.parent_id or comment.id,
        author_user_id=actor.user.id,
        author_token_id=actor.token.id if actor.token else None,
        body=body,
        mentions_agent=False,
    )
    db.add(reply)
    await db.flush()
    page = await db.get(Page, request.page_id)
    await comment_created(db, page, reply, None, actor.token is not None)


async def complete(
    db: AsyncSession,
    actor,
    request_id: uuid.UUID,
    *,
    result_version: int,
    reply: str | None,
    ip: str | None,
    context: str | None = None,
):
    _need_agent(actor)
    request = await _load(db, actor, request_id)
    if request.status != "claimed" or request.claimed_by_token_id != actor.token.id:
        raise AppError(
            409, "conflict", "Claim this request first, and finish before the claim ends"
        )
    version = await db.scalar(
        select(PageVersion).where(
            PageVersion.page_id == request.page_id, PageVersion.number == result_version
        )
    )
    if version is None:
        raise AppError(422, "validation_failed", "result_version is not a version of this page")
    if version.created_at <= request.created_at:
        raise AppError(
            422, "validation_failed", "result_version must be published after the request was made"
        )
    comment = await db.get(Comment, request.comment_id)
    if context and context.strip():
        page = await db.get(Page, request.page_id)
        pages_service.append_context(page, context, f"@{actor.user.handle}'s agent")
        await events.emit(db, page.id, "page.updated", {"context": True})
    request.status = "done"
    request.result_version_id = version.id
    request.claim_expires_at = None
    await _reply(
        db, actor, request, comment, reply or f"Published version {version.number}.", version.id
    )
    if request.requested_by and request.requested_by != actor.user.id:
        notifications.add(
            db,
            request.requested_by,
            "agent_done",
            page_id=request.page_id,
            request_id=request.id,
            actor_id=actor.user.id,
            body=f"Version {version.number} is live",
        )
    await events.emit(
        db,
        request.page_id,
        "request.completed",
        {"request_id": str(request.id), "result_version": version.number},
    )
    audit.record(
        db,
        action="request.complete",
        user_id=actor.user.id,
        token_id=actor.token.id,
        target_type="request",
        target_id=str(request.id),
        ip=ip,
        meta={"result_version": result_version},
    )
    await db.commit()
    return await _one(db, request)


async def dismiss(
    db: AsyncSession, actor, request_id: uuid.UUID, *, reason: str | None, ip: str | None
):
    request = await _load(db, actor, request_id)
    if request.status in ("done", "dismissed"):
        raise AppError(409, "conflict", f"This request is already {request.status}")
    request.status = "dismissed"
    request.dismiss_reason = reason
    request.claimed_by_token_id = None
    request.claim_expires_at = None
    if reason:
        comment = await db.get(Comment, request.comment_id)
        page = await db.get(Page, request.page_id)
        await _reply(db, actor, request, comment, reason, page.current_version_id)
    await events.emit(
        db, request.page_id, "request.dismissed", {"request_id": str(request.id), "reason": reason}
    )
    audit.record(
        db,
        action="request.dismiss",
        user_id=actor.user.id,
        token_id=actor.token.id if actor.token else None,
        target_type="request",
        target_id=str(request.id),
        ip=ip,
    )
    await db.commit()
    return await _one(db, request)


async def ask(db: AsyncSession, actor, request_id: uuid.UUID, *, question: str, ip: str | None):
    """The agent that holds a request asks the person something it cannot work out from the page."""
    _need_agent(actor)
    request = await _load(db, actor, request_id)
    if request.status != "claimed" or request.claimed_by_token_id != actor.token.id:
        raise AppError(409, "conflict", "Claim this request first, then ask your question")
    comment = await db.get(Comment, request.comment_id)
    page = await db.get(Page, request.page_id)
    await _reply(db, actor, request, comment, question, page.current_version_id)
    request.status = "needs_info"
    request.claimed_by_token_id = None
    request.claim_expires_at = None
    if request.requested_by:
        notifications.add(
            db,
            request.requested_by,
            "agent_question",
            page_id=request.page_id,
            request_id=request.id,
            actor_id=actor.user.id,
            body=f"An agent asks on {page.title}: {question[:80]}",
        )
    await events.emit(db, request.page_id, "request.needs_info", {"request_id": str(request.id)})
    audit.record(
        db,
        action="request.ask",
        user_id=actor.user.id,
        token_id=actor.token.id,
        target_type="request",
        target_id=str(request.id),
        ip=ip,
    )
    await db.commit()
    return await _one(db, request)


async def set_brief(db: AsyncSession, actor, request_id: uuid.UUID, *, brief: str, ip: str | None):
    """The asker or the page owner writes the brief. Changing it also answers a question."""
    request = await db.scalar(
        select(RevisionRequest).where(RevisionRequest.id == request_id).with_for_update()
    )
    if request is None:
        raise AppError(404, "not_found", "Request not found")
    await _page_for(db, actor, request, "request.create")
    page = await db.get(Page, request.page_id)
    if actor.user.id not in (request.requested_by, page.owner_id):
        raise AppError(403, "forbidden", "Only the person who asked, or the owner, can change this")
    if request.status in ("done", "dismissed"):
        raise AppError(409, "conflict", f"This request is already {request.status}")
    request.brief = brief or None
    if request.status == "needs_info":
        request.status = "open"
        await events.emit(db, request.page_id, "request.answered", {"request_id": str(request.id)})
    await events.emit(db, request.page_id, "request.updated", {"request_id": str(request.id)})
    audit.record(
        db,
        action="request.brief",
        user_id=actor.user.id,
        token_id=actor.token.id if actor.token else None,
        target_type="request",
        target_id=str(request.id),
        ip=ip,
    )
    await db.commit()
    return await _one(db, request)


def _name(user: User | None) -> str:
    if user is None:
        return "Someone"
    return user.display_name or f"@{user.handle}"


async def approve(db: AsyncSession, actor, request_id: uuid.UUID, *, ip: str | None):
    """A person lets their own agent take this request. The first person to ask wins.

    The request row is locked while we decide, so two people saying yes at the same moment are
    handled one after the other. The first finds it awaiting and wins. The second finds it already
    taken and is told by whom. The same person saying yes twice just gets the same answer.
    """
    if actor.token is not None:
        raise AppError(403, "forbidden", "A person says yes to this, not an agent token")
    request = await _load(db, actor, request_id)
    me = actor.user
    if request.status in ("done", "dismissed"):
        raise AppError(409, "conflict", f"This request is already {request.status}")
    if request.status != "awaiting":
        if request.approved_by_user_id == me.id:
            return await _one(db, request)
        taker = (
            await db.get(User, request.approved_by_user_id) if request.approved_by_user_id else None
        )
        raise AppError(409, "taken", f"{_name(taker)} got there first")
    if me.id not in await agents.with_agents(db, [me.id]):
        raise AppError(409, "no_agent", "Connect an agent first, then say yes")
    approvals.approve_for(request, me.id)
    await approvals.close_offers(db, request, me.id)
    page = await db.get(Page, request.page_id)
    comment = await db.get(Comment, request.comment_id)
    requester = await db.get(User, request.requested_by) if request.requested_by else None
    if requester is not None and requester.id != me.id:
        notifications.add(
            db,
            requester.id,
            "agent_approved",
            page_id=request.page_id,
            request_id=request.id,
            actor_id=me.id,
            body=comment.body,
        )
    await events.emit(
        db,
        request.page_id,
        "request.approved",
        {"request_id": str(request.id), "approved_by": me.handle},
    )
    audit.record(
        db,
        action="request.approve",
        user_id=me.id,
        target_type="request",
        target_id=str(request.id),
        ip=ip,
    )
    await db.commit()
    await approvals.wake(db, page, request, comment, requester, me.id)
    return await _one(db, request)


async def decline(db: AsyncSession, actor, request_id: uuid.UUID, *, ip: str | None):
    """A person says their agent will not take this one. It stays open for everyone else."""
    if actor.token is not None:
        raise AppError(403, "forbidden", "A person answers this, not an agent token")
    request = await _load(db, actor, request_id)
    if request.status != "awaiting":
        return await _one(db, request)
    offer = await db.get(RequestOffer, (request.id, actor.user.id))
    if offer is None:
        db.add(RequestOffer(request_id=request.id, user_id=actor.user.id, status="declined"))
    elif offer.status == "offered":
        offer.status = "declined"
    audit.record(
        db,
        action="request.decline",
        user_id=actor.user.id,
        target_type="request",
        target_id=str(request.id),
        ip=ip,
    )
    await db.commit()
    return await _one(db, request)
