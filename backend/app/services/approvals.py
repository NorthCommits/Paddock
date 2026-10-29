"""Whose agent may take a new request.

An @agent mention is a request for someone's agent. Nobody's agent works for someone else without a
yes, so each new request is routed first:

* The person who wrote it uses their own agent. That needs no yes. The owner of a page always does,
  and an editor does once they have an agent connected.
* Otherwise the owner and the editors who have an agent connected are asked. The first person to say
  yes gets it. A person can opt out ("never") or say yes in advance ("auto") in their settings.
* With nobody to ask, the request waits. It is never handed to an agent unasked.
"""

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, true, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import (
    AgentTrigger,
    Comment,
    Page,
    PageMember,
    RequestOffer,
    RevisionRequest,
    User,
)
from app.services import agents, emails, events, mailer, notifications, triggers


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Routed:
    """What happened to a request, so the caller can email and wake people after it commits."""

    approved_by: uuid.UUID | None = None
    offered: list[User] = field(default_factory=list)


async def people_who_can_act(db: AsyncSession, page: Page) -> list[uuid.UUID]:
    """The owner first, then editors in a fixed order, so choices are the same every time."""
    if page.visibility == "private":
        return [page.owner_id]
    editors = await db.scalars(
        select(PageMember.user_id)
        .where(PageMember.page_id == page.id, PageMember.role == "editor")
        .order_by(PageMember.user_id)
    )
    return [page.owner_id, *editors]


def approve_for(request: RevisionRequest, user_id: uuid.UUID) -> None:
    request.status = "open"
    request.approved_by_user_id = user_id
    request.approved_at = _now()


async def route(
    db: AsyncSession, page: Page, comment: Comment, request: RevisionRequest, requester: User
) -> Routed:
    """Decide whose agent may take this request. The caller commits."""
    people = await people_who_can_act(db, page)
    have = await agents.with_agents(db, [u for u in people if u != requester.id])
    if requester.id == page.owner_id or (
        requester.id in people and await _has_agent(db, requester)
    ):
        approve_for(request, requester.id)
        return Routed(approved_by=requester.id)

    users = {u.id: u for u in await db.scalars(select(User).where(User.id.in_(list(have))))}
    ask: list[User] = []
    for uid in people:
        user = users.get(uid)
        if user is None or user.agent_approval == "never":
            continue
        if user.agent_approval == "auto":
            approve_for(request, uid)
            notifications.add(
                db,
                requester.id,
                "agent_approved",
                page_id=page.id,
                request_id=request.id,
                actor_id=uid,
                body=comment.body,
            )
            return Routed(approved_by=uid)
        ask.append(user)

    request.status = "awaiting"
    request.approved_by_user_id = None
    request.approved_at = None
    await offer_to(db, page, comment, request, requester, ask)
    return Routed(offered=ask)


async def _has_agent(db: AsyncSession, user: User) -> bool:
    return user.id in await agents.with_agents(db, [user.id])


async def offer_to(
    db: AsyncSession,
    page: Page,
    comment: Comment,
    request: RevisionRequest,
    requester: User | None,
    people: list[User],
) -> None:
    for user in people:
        existing = await db.get(RequestOffer, (request.id, user.id))
        if existing is None:
            db.add(RequestOffer(request_id=request.id, user_id=user.id, status="offered"))
        elif existing.status != "declined":
            existing.status = "offered"
        notifications.add(
            db,
            user.id,
            "agent_offer",
            page_id=page.id,
            request_id=request.id,
            actor_id=requester.id if requester else None,
            body=comment.body,
        )
    await events.emit(
        db,
        page.id,
        "request.awaiting",
        {"request_id": str(request.id), "asked": len(people)},
    )


async def reset(db: AsyncSession, request: RevisionRequest) -> None:
    """Forget an earlier yes and the people asked, so the request can be routed again."""
    request.approved_by_user_id = None
    request.approved_at = None
    await db.execute(delete(RequestOffer).where(RequestOffer.request_id == request.id))


async def close_offers(db: AsyncSession, request: RevisionRequest, winner: uuid.UUID | None):
    """Mark the winner as won and everyone else still waiting as lost."""
    if winner is not None:
        await db.execute(
            update(RequestOffer)
            .where(RequestOffer.request_id == request.id, RequestOffer.user_id == winner)
            .values(status="won")
        )
    await db.execute(
        update(RequestOffer)
        .where(
            RequestOffer.request_id == request.id,
            RequestOffer.status == "offered",
            RequestOffer.user_id != winner if winner else true(),
        )
        .values(status="lost")
    )


def _who(user: User | None) -> str:
    if user is None:
        return "Someone"
    return user.display_name or f"@{user.handle}"


async def after_commit(
    db: AsyncSession,
    page: Page,
    comment: Comment,
    request: RevisionRequest,
    requester: User,
    routed: Routed,
) -> None:
    """Email the people asked and wake the approved agent. Call once the request is saved."""
    link = f"{get_settings().app_origin.rstrip('/')}/pages/{page.id}"
    quote = (comment.anchor or {}).get("selected") or (comment.anchor or {}).get("quote")
    for user in routed.offered:
        if user.notify_requests and not await _already_told(db, user, page, request):
            mailer.send_later(
                emails.agent_request(
                    user.email,
                    _who(requester),
                    page.title,
                    comment.body[:300],
                    str(quote)[:120] if quote else None,
                    link,
                )
            )
    await wake(db, page, request, comment, requester, routed.approved_by)


async def wake(
    db: AsyncSession,
    page: Page,
    request: RevisionRequest,
    comment: Comment,
    requester: User | None,
    approver: uuid.UUID | None,
) -> None:
    """Knock on the approver's saved Claude Code task, if they saved one."""
    if approver is None or await db.get(AgentTrigger, approver) is None:
        return
    triggers.wake_later(
        approver, triggers.request_text(page.title, _who(requester), comment.body, request.id)
    )


async def release(db: AsyncSession, request: RevisionRequest) -> None:
    """Ask again: the yes was never acted on. Everyone who has not declined is asked once more."""
    page = await db.get(Page, request.page_id)
    comment = await db.get(Comment, request.comment_id)
    requester = await db.get(User, request.requested_by) if request.requested_by else None
    asked = list(
        await db.scalars(
            select(User)
            .join(RequestOffer, RequestOffer.user_id == User.id)
            .where(RequestOffer.request_id == request.id, RequestOffer.status != "declined")
        )
    )
    request.status = "awaiting"
    request.approved_by_user_id = None
    request.approved_at = None
    await offer_to(db, page, comment, request, requester, asked)


async def _already_told(db: AsyncSession, user: User, page: Page, request: RevisionRequest) -> bool:
    """One email per wait: if another request on this page is still waiting on this person's yes,
    they have been told already. The bell shows every request."""
    others = await db.scalar(
        select(func.count())
        .select_from(RequestOffer)
        .join(RevisionRequest, RevisionRequest.id == RequestOffer.request_id)
        .where(
            RequestOffer.user_id == user.id,
            RequestOffer.status == "offered",
            RevisionRequest.page_id == page.id,
            RevisionRequest.id != request.id,
            RevisionRequest.status == "awaiting",
        )
    )
    return bool(others)
