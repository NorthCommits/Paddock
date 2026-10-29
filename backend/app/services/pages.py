"""Pages, versions and the rules around them (SDD sections 4.2, 5.1 and 5.2)."""

import base64
import re
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.policy import allowed
from app.core.signing import make_content_token
from app.db.models import Blob, Page, PageMember, PageVersion, User, VersionFile
from app.schemas.pages import PageOut, VersionDetailOut, VersionOut
from app.services import audit, events
from app.services.bundles import CheckedFile, fingerprint
from app.services.storage import get_storage, storage_key


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- access


async def role_for(db: AsyncSession, page: Page, user: User) -> str | None:
    """The person's role on a page.

    The owner always has full rights. Members count while the page is shared with members
    or by link. A private page is for its owner alone, whatever the member list says.
    """
    if page.owner_id == user.id:
        return "owner"
    if page.visibility == "private":
        return None
    return await db.scalar(
        select(PageMember.role).where(PageMember.page_id == page.id, PageMember.user_id == user.id)
    )


async def get_for_actor(
    db: AsyncSession, actor, page_id: uuid.UUID, action: str, lock: bool = False
) -> Page:
    """Load a page and check the action. Strangers get 404 so page ids cannot be probed."""
    query = select(Page).where(Page.id == page_id, Page.deleted_at.is_(None))
    if lock:
        query = query.with_for_update()
    page = await db.scalar(query)
    role = await role_for(db, page, actor.user) if page else None
    if page is None or role is None:
        raise AppError(404, "not_found", "Page not found")
    if not allowed(action, role, actor.scopes):
        raise AppError(
            403, "forbidden", f"This action needs a higher role or a token scope ({action})"
        )
    return page


# ---------------------------------------------------------------- slugs


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60].strip("-")
    return slug or "page"


async def _free_slug(db: AsyncSession, owner_id: uuid.UUID, base: str) -> str:
    for n in range(1, 100):
        candidate = base if n == 1 else f"{base[: 60 - len(str(n)) - 1]}-{n}"
        taken = await db.scalar(
            select(Page.id).where(
                Page.owner_id == owner_id, Page.slug == candidate, Page.deleted_at.is_(None)
            )
        )
        if taken is None:
            return candidate
    raise AppError(409, "conflict", "Could not find a free slug, choose one")


# ---------------------------------------------------------------- building output


async def _version_outs(
    db: AsyncSession, versions: list[PageVersion]
) -> dict[uuid.UUID, VersionOut]:
    restored_ids = {v.rolled_back_from for v in versions if v.rolled_back_from}
    numbers: dict[uuid.UUID, int] = {}
    if restored_ids:
        rows = await db.execute(
            select(PageVersion.id, PageVersion.number).where(PageVersion.id.in_(restored_ids))
        )
        numbers = {row.id: row.number for row in rows}
    return {
        v.id: VersionOut(
            id=v.id,
            number=v.number,
            message=v.message,
            entry_path=v.entry_path,
            total_bytes=v.total_bytes,
            file_count=v.file_count,
            rolled_back_from=numbers.get(v.rolled_back_from) if v.rolled_back_from else None,
            author_user_id=v.author_user_id,
            by_agent=v.author_token_id is not None,
            created_at=v.created_at,
        )
        for v in versions
    }


async def page_outs(db: AsyncSession, pages: list[Page], user: User) -> list[PageOut]:
    version_ids = [p.current_version_id for p in pages if p.current_version_id]
    versions = (
        list(await db.scalars(select(PageVersion).where(PageVersion.id.in_(version_ids))))
        if version_ids
        else []
    )
    outs = await _version_outs(db, versions)
    owners = {
        row.id: row.handle
        for row in await db.execute(
            select(User.id, User.handle).where(User.id.in_({p.owner_id for p in pages}))
        )
    }
    member_roles = {
        row.page_id: row.role
        for row in await db.execute(
            select(PageMember.page_id, PageMember.role).where(
                PageMember.user_id == user.id, PageMember.page_id.in_([p.id for p in pages])
            )
        )
    }
    return [
        PageOut(
            id=p.id,
            slug=p.slug,
            title=p.title,
            visibility=p.visibility,
            owner_handle=owners.get(p.owner_id, ""),
            role="owner" if p.owner_id == user.id else member_roles.get(p.id, "viewer"),
            current_version=outs.get(p.current_version_id) if p.current_version_id else None,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in pages
    ]


async def page_out(db: AsyncSession, page: Page, user: User) -> PageOut:
    return (await page_outs(db, [page], user))[0]


async def version_out(db: AsyncSession, version: PageVersion) -> VersionOut:
    return (await _version_outs(db, [version]))[version.id]


# ---------------------------------------------------------------- writing versions


async def _store_files(files: list[CheckedFile]) -> None:
    storage = get_storage()
    for f in files:
        await storage.put(f.sha256, f.data)


async def _next_number(db: AsyncSession, page_id: uuid.UUID) -> int:
    current = await db.scalar(
        select(func.max(PageVersion.number)).where(PageVersion.page_id == page_id)
    )
    return (current or 0) + 1


async def _add_version(
    db: AsyncSession,
    page: Page,
    actor,
    *,
    entries: list[tuple[str, str, int, str]],  # (path, sha256, size, content type)
    entry_path: str,
    message: str | None,
    content_hash: str,
    rolled_back_from: uuid.UUID | None = None,
) -> PageVersion:
    """Insert a version and its files. The caller holds the page lock and commits."""
    version = PageVersion(
        page_id=page.id,
        number=await _next_number(db, page.id),
        message=message,
        author_user_id=actor.user.id,
        author_token_id=actor.token.id if actor.token else None,
        entry_path=entry_path,
        total_bytes=sum(e[2] for e in entries),
        file_count=len(entries),
        content_hash=content_hash,
        rolled_back_from=rolled_back_from,
    )
    db.add(version)
    await db.flush()

    await db.execute(
        pg_insert(Blob)
        .values(
            [
                {"sha256": sha, "size_bytes": size, "storage_key": storage_key(sha)}
                for _, sha, size, _ in entries
            ]
        )
        .on_conflict_do_nothing(index_elements=[Blob.sha256])
    )
    await db.execute(
        update(Blob)
        .where(Blob.sha256.in_([e[1] for e in entries]))
        .values(ref_count=Blob.ref_count + 1)
    )
    db.add_all(
        VersionFile(
            version_id=version.id, path=path, sha256=sha, size_bytes=size, content_type=ctype
        )
        for path, sha, size, ctype in entries
    )
    page.current_version_id = version.id
    page.updated_at = _now()
    await db.flush()
    return version


async def create(
    db: AsyncSession,
    actor,
    *,
    title: str,
    slug: str | None,
    message: str | None,
    files: list[CheckedFile],
    entry_path: str,
    ip: str | None,
) -> tuple[Page, PageVersion]:
    if "pages:write" not in actor.scopes:
        raise AppError(403, "forbidden", "This token lacks the pages:write scope")
    await _store_files(files)
    owner_id = actor.user.id
    final_slug = slug or await _free_slug(db, owner_id, slugify(title))
    page = Page(owner_id=owner_id, slug=final_slug, title=title)
    db.add(page)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise AppError(
            409, "conflict", f"You already have a page with the slug '{final_slug}'"
        ) from None

    entries = [(f.path, f.sha256, f.size, f.content_type) for f in files]
    version = await _add_version(
        db,
        page,
        actor,
        entries=entries,
        entry_path=entry_path,
        message=message,
        content_hash=fingerprint([(e[0], e[1]) for e in entries], entry_path),
    )
    audit.record(
        db,
        action="page.create",
        user_id=actor.user.id,
        token_id=actor.token.id if actor.token else None,
        target_type="page",
        target_id=str(page.id),
        ip=ip,
        meta={"slug": page.slug, "version": version.number},
    )
    await events.emit(
        db,
        page.id,
        "version.published",
        {
            "version": version.number,
            "message": version.message,
            "by_agent": actor.token is not None,
        },
    )
    await db.commit()
    return page, version


async def publish(
    db: AsyncSession,
    actor,
    page_id: uuid.UUID,
    *,
    files: list[CheckedFile],
    entry_path: str,
    message: str | None,
    base_version: int | None,
    ip: str | None,
) -> tuple[Page, PageVersion, bool]:
    # Check the permission before doing any work, then lock the page for the whole publish.
    await get_for_actor(db, actor, page_id, "version.publish")
    await _store_files(files)
    page = await get_for_actor(db, actor, page_id, "version.publish", lock=True)

    current = (
        await db.get(PageVersion, page.current_version_id) if page.current_version_id else None
    )
    if base_version is not None and (current is None or current.number != base_version):
        now = current.number if current else 0
        raise AppError(409, "conflict", f"The page is now at version {now}, not {base_version}")

    entries = [(f.path, f.sha256, f.size, f.content_type) for f in files]
    content_hash = fingerprint([(e[0], e[1]) for e in entries], entry_path)
    if current is not None and current.content_hash == content_hash:
        await db.commit()  # releases the lock; nothing changed
        return page, current, False

    version = await _add_version(
        db,
        page,
        actor,
        entries=entries,
        entry_path=entry_path,
        message=message,
        content_hash=content_hash,
    )
    audit.record(
        db,
        action="version.publish",
        user_id=actor.user.id,
        token_id=actor.token.id if actor.token else None,
        target_type="page",
        target_id=str(page.id),
        ip=ip,
        meta={"version": version.number, "files": version.file_count},
    )
    await events.emit(
        db,
        page.id,
        "version.published",
        {
            "version": version.number,
            "message": version.message,
            "by_agent": actor.token is not None,
        },
    )
    await db.commit()
    return page, version, True


async def rollback(
    db: AsyncSession, actor, page_id: uuid.UUID, number: int, ip: str | None
) -> tuple[Page, PageVersion, bool]:
    """Publish an earlier version again as the newest one."""
    page = await get_for_actor(db, actor, page_id, "version.publish", lock=True)
    old = await db.scalar(
        select(PageVersion).where(PageVersion.page_id == page.id, PageVersion.number == number)
    )
    if old is None:
        raise AppError(404, "not_found", "Version not found")
    current = (
        await db.get(PageVersion, page.current_version_id) if page.current_version_id else None
    )
    if current is not None and current.content_hash == old.content_hash:
        await db.commit()
        return page, current, False

    rows = list(await db.scalars(select(VersionFile).where(VersionFile.version_id == old.id)))
    entries = [(r.path, r.sha256, r.size_bytes, r.content_type) for r in rows]
    version = await _add_version(
        db,
        page,
        actor,
        entries=entries,
        entry_path=old.entry_path,
        message=f"Restored version {old.number}",
        content_hash=old.content_hash,
        rolled_back_from=old.id,
    )
    audit.record(
        db,
        action="version.rollback",
        user_id=actor.user.id,
        token_id=actor.token.id if actor.token else None,
        target_type="page",
        target_id=str(page.id),
        ip=ip,
        meta={"restored": old.number, "version": version.number},
    )
    await events.emit(
        db,
        page.id,
        "version.rolled_back",
        {"version": version.number, "restored": old.number, "by_agent": actor.token is not None},
    )
    await db.commit()
    return page, version, True


# ---------------------------------------------------------------- reading


def _encode_cursor(*parts: str) -> str:
    return base64.urlsafe_b64encode("|".join(parts).encode()).decode()


def _decode_cursor(cursor: str, count: int) -> list[str]:
    try:
        parts = base64.urlsafe_b64decode(cursor.encode()).decode().split("|")
    except ValueError:
        parts = []
    if len(parts) != count:
        raise AppError(422, "validation_failed", "Invalid cursor")
    return parts


async def list_pages(
    db: AsyncSession, actor, *, limit: int, cursor: str | None, slug: str | None
) -> tuple[list[Page], str | None]:
    shared_with_me = select(PageMember.page_id).where(PageMember.user_id == actor.user.id)
    query = select(Page).where(
        Page.deleted_at.is_(None),
        or_(
            Page.owner_id == actor.user.id,
            and_(Page.visibility != "private", Page.id.in_(shared_with_me)),
        ),
    )
    if slug:
        query = query.where(Page.slug == slug)
    if cursor:
        stamp, page_id = _decode_cursor(cursor, 2)
        try:
            at, pid = datetime.fromisoformat(stamp), uuid.UUID(page_id)
        except ValueError:
            raise AppError(422, "validation_failed", "Invalid cursor") from None
        query = query.where((Page.updated_at, Page.id) < (at, pid))
    rows = list(
        await db.scalars(query.order_by(Page.updated_at.desc(), Page.id.desc()).limit(limit + 1))
    )
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = _encode_cursor(rows[-1].updated_at.isoformat(), str(rows[-1].id))
    return rows, next_cursor


async def list_versions(
    db: AsyncSession, page: Page, *, limit: int, cursor: str | None
) -> tuple[list[PageVersion], str | None]:
    query = select(PageVersion).where(PageVersion.page_id == page.id)
    if cursor:
        (before,) = _decode_cursor(cursor, 1)
        if not before.isdigit():
            raise AppError(422, "validation_failed", "Invalid cursor")
        query = query.where(PageVersion.number < int(before))
    rows = list(await db.scalars(query.order_by(PageVersion.number.desc()).limit(limit + 1)))
    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        next_cursor = _encode_cursor(str(rows[-1].number))
    return rows, next_cursor


async def get_version(db: AsyncSession, page: Page, number: int) -> PageVersion:
    version = await db.scalar(
        select(PageVersion).where(PageVersion.page_id == page.id, PageVersion.number == number)
    )
    if version is None:
        raise AppError(404, "not_found", "Version not found")
    return version


async def version_detail(db: AsyncSession, version: PageVersion) -> VersionDetailOut:
    files = list(
        await db.scalars(
            select(VersionFile)
            .where(VersionFile.version_id == version.id)
            .order_by(VersionFile.path)
        )
    )
    base = await version_out(db, version)
    return VersionDetailOut(**base.model_dump(), files=files)  # type: ignore[arg-type]


# ---------------------------------------------------------------- editing and deleting


async def update_page(
    db: AsyncSession,
    actor,
    page_id: uuid.UUID,
    *,
    title: str | None,
    slug: str | None,
    visibility: str | None = None,
    ip: str | None,
) -> Page:
    page = await get_for_actor(db, actor, page_id, "page.update", lock=True)
    changes = {}
    if visibility and visibility != page.visibility:
        page.visibility = visibility
        changes["visibility"] = visibility
    if title is not None and title.strip() and title.strip() != page.title:
        page.title = title.strip()
        changes["title"] = page.title
    if slug and slug != page.slug:
        page.slug = slug
        changes["slug"] = slug
    if not changes:
        await db.commit()
        return page
    page.updated_at = _now()
    audit.record(
        db,
        action="page.update",
        user_id=actor.user.id,
        token_id=actor.token.id if actor.token else None,
        target_type="page",
        target_id=str(page.id),
        ip=ip,
        meta=changes,
    )
    try:
        await events.emit(db, page.id, "page.updated", changes)  # this also saves the change
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise AppError(409, "conflict", f"You already have a page with the slug '{slug}'") from None
    return page


async def delete_page(db: AsyncSession, actor, page_id: uuid.UUID, ip: str | None) -> None:
    page = await get_for_actor(db, actor, page_id, "page.delete", lock=True)
    page.deleted_at = _now()
    audit.record(
        db,
        action="page.delete",
        user_id=actor.user.id,
        token_id=actor.token.id if actor.token else None,
        target_type="page",
        target_id=str(page.id),
        ip=ip,
    )
    await events.emit(db, page.id, "page.deleted", {})
    await db.commit()


# ---------------------------------------------------------------- view links


async def view_url(
    db: AsyncSession, actor, page_id: uuid.UUID, number: int | None
) -> tuple[str, datetime, int]:
    page = await get_for_actor(db, actor, page_id, "page.view")
    return await view_url_for(db, page, number)


async def view_url_for(
    db: AsyncSession, page: Page, number: int | None
) -> tuple[str, datetime, int]:
    """A signed content link for a page the caller is already allowed to see, with the version
    number it shows (so the screen can tell a new version from a refreshed link)."""
    if number is None:
        if page.current_version_id is None:
            raise AppError(404, "not_found", "This page has no versions yet")
        current = await db.get(PageVersion, page.current_version_id)
        assert current is not None
        version = current
    else:
        version = await get_version(db, page, number)
    settings = get_settings()
    token, expires = make_content_token(
        page.id, version.number, settings.content_token_minutes * 60
    )
    entry = version.entry_path
    url = f"{settings.content_origin.rstrip('/')}/c/{token}/{entry}"
    return url, datetime.fromtimestamp(expires, UTC), version.number
