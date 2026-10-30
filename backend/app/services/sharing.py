"""Members, invitations and share links (SDD sections 4.3 and 5.5)."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.policy import allowed
from app.core.security import new_secret, sha256_hex
from app.db.models import Page, PageInvite, PageMember, PageVersion, ShareLink, User
from app.schemas.sharing import (
    InviteCreatedOut,
    InviteOut,
    InvitePreviewOut,
    LinkCreatedOut,
    LinkOut,
    MemberOut,
    SharedOut,
)
from app.services import audit, emails, events, mailer, pages

INVITE_DAYS = 7
MAX_MEMBERS = 50
MAX_INVITES = 50
MAX_LINKS = 20

# private < members < link. Sharing a page widens its visibility to at least what is needed.
LEVEL = {"private": 0, "members": 1, "link": 2}

BAD_LINK = AppError(404, "not_found", "This link is invalid, expired or has been turned off.")
BAD_INVITE = AppError(404, "not_found", "This invitation is invalid, expired or already used.")


def _now() -> datetime:
    return datetime.now(UTC)


def _widen(page: Page, to: str) -> None:
    if LEVEL[page.visibility] < LEVEL[to]:
        page.visibility = to


def _actor_fields(actor) -> dict:
    return {"user_id": actor.user.id, "token_id": actor.token.id if actor.token else None}


# ---------------------------------------------------------------- members


async def list_members(db: AsyncSession, actor, page_id: uuid.UUID) -> list[MemberOut]:
    page = await pages.get_for_actor(db, actor, page_id, "page.manage_sharing")
    rows = await db.execute(
        select(PageMember, User)
        .join(User, User.id == PageMember.user_id)
        .where(PageMember.page_id == page.id)
        .order_by(PageMember.created_at)
    )
    return [
        MemberOut(
            user_id=u.id,
            handle=u.handle,
            display_name=u.display_name,
            email=u.email,
            role=m.role,
            created_at=m.created_at,
        )
        for m, u in rows
    ]


async def update_member(
    db: AsyncSession, actor, page_id: uuid.UUID, user_id: uuid.UUID, role: str, ip: str | None
) -> None:
    page = await pages.get_for_actor(db, actor, page_id, "page.manage_sharing")
    member = await db.get(PageMember, (page.id, user_id))
    if member is None:
        raise AppError(404, "not_found", "Member not found")
    if member.role != role:
        member.role = role
        audit.record(
            db,
            action="member.update",
            **_actor_fields(actor),
            target_type="page",
            target_id=str(page.id),
            ip=ip,
            meta={"member": str(user_id), "role": role},
        )
    await db.commit()


async def remove_member(
    db: AsyncSession, actor, page_id: uuid.UUID, user_id: uuid.UUID, ip: str | None
) -> None:
    """The owner can remove anyone. A member can remove themselves (leave the page)."""
    page = await pages.get_for_actor(db, actor, page_id, "page.view")
    role = await pages.role_for(db, page, actor.user)
    leaving = user_id == actor.user.id and role != "owner"
    if not leaving and not allowed("page.manage_sharing", role, actor.scopes):
        raise AppError(403, "forbidden", "Only the owner can remove members")
    result = await db.execute(
        delete(PageMember).where(PageMember.page_id == page.id, PageMember.user_id == user_id)
    )
    if result.rowcount == 0:
        raise AppError(404, "not_found", "Member not found")
    audit.record(
        db,
        action="member.remove",
        **_actor_fields(actor),
        target_type="page",
        target_id=str(page.id),
        ip=ip,
        meta={"member": str(user_id), "left": leaving},
    )
    await events.emit(db, page.id, "member.removed", {"user_id": str(user_id), "left": leaving})
    await db.commit()


# ---------------------------------------------------------------- invitations


def _invite_out(i: PageInvite) -> InviteOut:
    return InviteOut(
        id=i.id,
        email=i.email,
        role=i.role,
        created_at=i.created_at,
        expires_at=i.expires_at,
        expired=i.expires_at <= _now(),
    )


async def create_invite(
    db: AsyncSession,
    actor,
    page_id: uuid.UUID,
    email: str,
    role: str,
    ip: str | None,
    message: str | None = None,
) -> InviteCreatedOut:
    page = await pages.get_for_actor(db, actor, page_id, "page.manage_sharing", lock=True)
    owner = await db.get(User, page.owner_id)
    assert owner is not None
    if email == owner.email:
        raise AppError(422, "validation_failed", "That is the owner's email address")

    existing = await db.scalar(
        select(PageMember.role)
        .join(User, User.id == PageMember.user_id)
        .where(PageMember.page_id == page.id, User.email == email)
    )
    if existing == role:
        raise AppError(409, "conflict", "That person already has this access")

    # A new invitation for the same address replaces the old one.
    await db.execute(
        delete(PageInvite).where(
            PageInvite.page_id == page.id,
            PageInvite.email == email,
            PageInvite.accepted_at.is_(None),
        )
    )
    pending = await db.scalar(
        select(func.count())
        .select_from(PageInvite)
        .where(PageInvite.page_id == page.id, PageInvite.accepted_at.is_(None))
    )
    if (pending or 0) >= MAX_INVITES:
        raise AppError(409, "conflict", "Too many pending invitations. Revoke some first.")
    members = await db.scalar(
        select(func.count()).select_from(PageMember).where(PageMember.page_id == page.id)
    )
    if (members or 0) >= MAX_MEMBERS:
        raise AppError(409, "conflict", "This page has reached its member limit")

    raw = new_secret()
    invite = PageInvite(
        page_id=page.id,
        email=email,
        role=role,
        token_hash=sha256_hex(raw),
        invited_by=actor.user.id,
        expires_at=_now() + timedelta(days=INVITE_DAYS),
    )
    db.add(invite)
    _widen(page, "members")
    await db.flush()
    audit.record(
        db,
        action="invite.create",
        **_actor_fields(actor),
        target_type="page",
        target_id=str(page.id),
        ip=ip,
        meta={"email": email, "role": role},
    )
    await db.commit()

    url = f"{get_settings().app_origin}/invites/{raw}"
    emailed = await mailer.send_quietly(
        emails.page_invite(
            email,
            actor.user.display_name,
            page.title,
            role,
            url,
            INVITE_DAYS,
            message=message,
            reply_to=actor.user.email,
        )
    )
    return InviteCreatedOut(**_invite_out(invite).model_dump(), accept_url=url, emailed=emailed)


async def list_invites(db: AsyncSession, actor, page_id: uuid.UUID) -> list[InviteOut]:
    page = await pages.get_for_actor(db, actor, page_id, "page.manage_sharing")
    rows = await db.scalars(
        select(PageInvite)
        .where(PageInvite.page_id == page.id, PageInvite.accepted_at.is_(None))
        .order_by(PageInvite.created_at.desc())
    )
    return [_invite_out(i) for i in rows]


async def revoke_invite(
    db: AsyncSession, actor, page_id: uuid.UUID, invite_id: uuid.UUID, ip: str | None
) -> None:
    page = await pages.get_for_actor(db, actor, page_id, "page.manage_sharing")
    result = await db.execute(
        delete(PageInvite).where(
            PageInvite.id == invite_id,
            PageInvite.page_id == page.id,
            PageInvite.accepted_at.is_(None),
        )
    )
    if result.rowcount == 0:
        raise AppError(404, "not_found", "Invitation not found")
    audit.record(
        db,
        action="invite.revoke",
        **_actor_fields(actor),
        target_type="page",
        target_id=str(page.id),
        ip=ip,
    )
    await db.commit()


async def _open_invite(db: AsyncSession, raw: str, lock: bool = False) -> PageInvite:
    query = select(PageInvite).where(
        PageInvite.token_hash == sha256_hex(raw),
        PageInvite.accepted_at.is_(None),
        PageInvite.expires_at > _now(),
    )
    invite = await db.scalar(query.with_for_update() if lock else query)
    if invite is None:
        raise BAD_INVITE
    return invite


async def preview_invite(db: AsyncSession, raw: str) -> InvitePreviewOut:
    invite = await _open_invite(db, raw)
    page = await db.scalar(select(Page).where(Page.id == invite.page_id, Page.deleted_at.is_(None)))
    if page is None:
        raise BAD_INVITE
    owner = await db.get(User, page.owner_id)
    inviter = await db.get(User, invite.invited_by) if invite.invited_by else None
    assert owner is not None
    return InvitePreviewOut(
        page_title=page.title,
        owner_handle=owner.handle,
        invited_by=inviter.display_name if inviter else None,
        email=invite.email,
        role=invite.role,
        expires_at=invite.expires_at,
    )


async def accept_invite(db: AsyncSession, user: User, raw: str, ip: str | None) -> tuple[Page, str]:
    """Accepting needs an account whose confirmed email is the one that was invited."""
    invite = await _open_invite(db, raw, lock=True)
    page = await db.scalar(select(Page).where(Page.id == invite.page_id, Page.deleted_at.is_(None)))
    if page is None:
        raise BAD_INVITE
    if user.email_verified_at is None:
        raise AppError(
            403, "email_not_verified", "Confirm your email address first, then open the link again."
        )
    if user.email != invite.email:
        raise AppError(
            403,
            "forbidden",
            f"This invitation was sent to {invite.email}. Sign in with that address to accept it.",
        )
    if page.owner_id == user.id:
        raise AppError(409, "conflict", "You own this page")

    await db.execute(
        pg_insert(PageMember)
        .values(page_id=page.id, user_id=user.id, role=invite.role, invited_by=invite.invited_by)
        .on_conflict_do_update(
            index_elements=[PageMember.page_id, PageMember.user_id], set_={"role": invite.role}
        )
    )
    invite.accepted_at = _now()
    audit.record(
        db,
        action="member.add",
        user_id=user.id,
        target_type="page",
        target_id=str(page.id),
        ip=ip,
        meta={"role": invite.role},
    )
    await events.emit(db, page.id, "member.added", {"user_id": str(user.id), "role": invite.role})
    await db.commit()
    return page, invite.role


# ---------------------------------------------------------------- share links


def _link_out(link: ShareLink) -> LinkOut:
    return LinkOut(
        id=link.id,
        role=link.role,
        created_at=link.created_at,
        expires_at=link.expires_at,
        expired=link.expires_at is not None and link.expires_at <= _now(),
    )


async def create_link(
    db: AsyncSession,
    actor,
    page_id: uuid.UUID,
    role: str,
    expires_in_days: int | None,
    ip: str | None,
) -> LinkCreatedOut:
    page = await pages.get_for_actor(db, actor, page_id, "page.manage_sharing", lock=True)
    live = await db.scalar(
        select(func.count())
        .select_from(ShareLink)
        .where(ShareLink.page_id == page.id, ShareLink.revoked_at.is_(None))
    )
    if (live or 0) >= MAX_LINKS:
        raise AppError(409, "conflict", "Too many share links. Revoke some first.")
    raw = new_secret()
    link = ShareLink(
        page_id=page.id,
        token_hash=sha256_hex(raw),
        role=role,
        created_by=actor.user.id,
        expires_at=_now() + timedelta(days=expires_in_days) if expires_in_days else None,
    )
    db.add(link)
    _widen(page, "link")
    await db.flush()
    audit.record(
        db,
        action="link.create",
        **_actor_fields(actor),
        target_type="page",
        target_id=str(page.id),
        ip=ip,
        meta={"role": role, "expires_in_days": expires_in_days},
    )
    await db.commit()
    url = f"{get_settings().app_origin}/s/{raw}"
    return LinkCreatedOut(**_link_out(link).model_dump(), url=url)


async def list_links(db: AsyncSession, actor, page_id: uuid.UUID) -> list[LinkOut]:
    page = await pages.get_for_actor(db, actor, page_id, "page.manage_sharing")
    rows = await db.scalars(
        select(ShareLink)
        .where(ShareLink.page_id == page.id, ShareLink.revoked_at.is_(None))
        .order_by(ShareLink.created_at.desc())
    )
    return [_link_out(link) for link in rows]


async def revoke_link(
    db: AsyncSession, actor, page_id: uuid.UUID, link_id: uuid.UUID, ip: str | None
) -> None:
    page = await pages.get_for_actor(db, actor, page_id, "page.manage_sharing")
    link = await db.scalar(
        select(ShareLink).where(
            ShareLink.id == link_id, ShareLink.page_id == page.id, ShareLink.revoked_at.is_(None)
        )
    )
    if link is None:
        raise AppError(404, "not_found", "Link not found")
    link.revoked_at = _now()
    audit.record(
        db,
        action="link.revoke",
        **_actor_fields(actor),
        target_type="page",
        target_id=str(page.id),
        ip=ip,
    )
    await db.commit()


async def resolve_link(db: AsyncSession, raw: str) -> tuple[Page, ShareLink]:
    """Find the page a link opens. Anything wrong with it gives the same 404."""
    link = await db.scalar(
        select(ShareLink).where(
            ShareLink.token_hash == sha256_hex(raw), ShareLink.revoked_at.is_(None)
        )
    )
    if link is None or (link.expires_at is not None and link.expires_at <= _now()):
        raise BAD_LINK
    page = await db.scalar(select(Page).where(Page.id == link.page_id, Page.deleted_at.is_(None)))
    # Links only work while the page is set to "link". Narrowing it switches them all off.
    if page is None or page.visibility != "link":
        raise BAD_LINK
    return page, link


async def shared_page(db: AsyncSession, raw: str) -> SharedOut:
    page, link = await resolve_link(db, raw)
    owner = await db.get(User, page.owner_id)
    number = None
    if page.current_version_id:
        current = await db.get(PageVersion, page.current_version_id)
        number = current.number if current else None
    assert owner is not None
    return SharedOut(
        page_id=page.id,
        title=page.title,
        owner_handle=owner.handle,
        role=link.role,
        version_number=number,
        updated_at=page.updated_at,
    )


async def shared_view_url(db: AsyncSession, raw: str):
    page, _ = await resolve_link(db, raw)
    return await pages.view_url_for(db, page, None)
