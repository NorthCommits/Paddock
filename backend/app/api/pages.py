import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ValidationError

from app.api.bundle_input import read_bundle_request
from app.api.deps import ActorDep, DbDep, VerifiedActorDep, client_ip, require_scope
from app.core.config import get_settings
from app.core.errors import AppError
from app.schemas.pages import (
    PageFields,
    PageListOut,
    PageOut,
    PageUpdate,
    PublishOut,
    VersionDetailOut,
    VersionFields,
    VersionListOut,
    ViewUrlIn,
    ViewUrlOut,
)
from app.services import pages
from app.services.bundles import check_bundle

router = APIRouter(prefix="/v1/pages", tags=["pages"])


def _validated[T: BaseModel](model: type[T], fields: dict) -> T:
    try:
        return model.model_validate(fields)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"])
        raise AppError(422, "validation_failed", f"{where}: {first['msg']}") from None


@router.post("", status_code=201, response_model=PublishOut)
async def create_page(request: Request, db: DbDep, actor: VerifiedActorDep):
    """Create a page and its first version. Send multipart/form-data or JSON (see bundle_input)."""
    upload = await read_bundle_request(request)
    fields = _validated(PageFields, upload.fields)
    files, entry = check_bundle(upload.files, fields.entry_path, get_settings())
    page, version = await pages.create(
        db,
        actor,
        title=fields.title,
        slug=fields.slug,
        message=fields.message,
        files=files,
        entry_path=entry,
        ip=client_ip(request),
    )
    return PublishOut(
        page=await pages.page_out(db, page),
        version=await pages.version_out(db, version),
        created=True,
    )


@router.get("", response_model=PageListOut, dependencies=[Depends(require_scope("pages:read"))])
async def list_pages(
    db: DbDep,
    actor: ActorDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
    slug: str | None = None,
):
    rows, next_cursor = await pages.list_pages(db, actor, limit=limit, cursor=cursor, slug=slug)
    return PageListOut(items=await pages.page_outs(db, rows), next_cursor=next_cursor)


@router.get("/{page_id}", response_model=PageOut)
async def get_page(page_id: uuid.UUID, db: DbDep, actor: ActorDep):
    page = await pages.get_for_actor(db, actor, page_id, "page.view")
    return await pages.page_out(db, page)


@router.patch("/{page_id}", response_model=PageOut)
async def update_page(
    page_id: uuid.UUID, body: PageUpdate, request: Request, db: DbDep, actor: VerifiedActorDep
):
    page = await pages.update_page(
        db, actor, page_id, title=body.title, slug=body.slug, ip=client_ip(request)
    )
    return await pages.page_out(db, page)


@router.delete("/{page_id}", status_code=204)
async def delete_page(page_id: uuid.UUID, request: Request, db: DbDep, actor: ActorDep):
    await pages.delete_page(db, actor, page_id, client_ip(request))
    return Response(status_code=204)


@router.post("/{page_id}/versions", response_model=PublishOut)
async def publish_version(
    page_id: uuid.UUID, request: Request, response: Response, db: DbDep, actor: VerifiedActorDep
):
    """Publish a new version. Identical files return the current version with created=false."""
    upload = await read_bundle_request(request)
    fields = _validated(VersionFields, upload.fields)
    files, entry = check_bundle(upload.files, fields.entry_path, get_settings())
    page, version, created = await pages.publish(
        db,
        actor,
        page_id,
        files=files,
        entry_path=entry,
        message=fields.message,
        base_version=fields.base_version,
        ip=client_ip(request),
    )
    response.status_code = 201 if created else 200
    return PublishOut(
        page=await pages.page_out(db, page),
        version=await pages.version_out(db, version),
        created=created,
    )


@router.get("/{page_id}/versions", response_model=VersionListOut)
async def list_versions(
    page_id: uuid.UUID,
    db: DbDep,
    actor: ActorDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
):
    page = await pages.get_for_actor(db, actor, page_id, "page.view")
    rows, next_cursor = await pages.list_versions(db, page, limit=limit, cursor=cursor)
    outs = await pages._version_outs(db, rows)
    return VersionListOut(items=[outs[v.id] for v in rows], next_cursor=next_cursor)


@router.get("/{page_id}/versions/{number}", response_model=VersionDetailOut)
async def get_version(page_id: uuid.UUID, number: int, db: DbDep, actor: ActorDep):
    page = await pages.get_for_actor(db, actor, page_id, "page.view")
    version = await pages.get_version(db, page, number)
    return await pages.version_detail(db, version)


@router.post("/{page_id}/versions/{number}/rollback", response_model=PublishOut)
async def rollback_version(
    page_id: uuid.UUID,
    number: int,
    request: Request,
    response: Response,
    db: DbDep,
    actor: VerifiedActorDep,
):
    page, version, created = await pages.rollback(db, actor, page_id, number, client_ip(request))
    response.status_code = 201 if created else 200
    return PublishOut(
        page=await pages.page_out(db, page),
        version=await pages.version_out(db, version),
        created=created,
    )


@router.post("/{page_id}/view-url", response_model=ViewUrlOut)
async def view_url(page_id: uuid.UUID, db: DbDep, actor: ActorDep, body: ViewUrlIn | None = None):
    """A short-lived link to the page on the content origin."""
    url, expires = await pages.view_url(db, actor, page_id, body.version if body else None)
    return ViewUrlOut(url=url, expires_at=expires)
