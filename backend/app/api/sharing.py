import uuid

from fastapi import APIRouter, Depends, Request

from app.api.deps import ActorDep, DbDep, PersonDep, VerifiedActorDep, client_ip
from app.core.ratelimit import limit
from app.schemas.pages import PageOut, ViewUrlOut
from app.schemas.sharing import (
    InviteCreatedOut,
    InviteIn,
    InviteOut,
    InvitePreviewOut,
    LinkCreatedOut,
    LinkIn,
    LinkOut,
    MemberOut,
    MemberUpdate,
    SharedOut,
)
from app.services import pages, sharing

# Everything the owner does to share one page.
router = APIRouter(prefix="/v1/pages/{page_id}", tags=["sharing"])


@router.get("/members", response_model=list[MemberOut])
async def list_members(page_id: uuid.UUID, db: DbDep, actor: ActorDep):
    return await sharing.list_members(db, actor, page_id)


@router.patch("/members/{user_id}", status_code=204)
async def update_member(
    page_id: uuid.UUID,
    user_id: uuid.UUID,
    body: MemberUpdate,
    request: Request,
    db: DbDep,
    actor: ActorDep,
):
    await sharing.update_member(db, actor, page_id, user_id, body.role, client_ip(request))


@router.delete("/members/{user_id}", status_code=204)
async def remove_member(
    page_id: uuid.UUID, user_id: uuid.UUID, request: Request, db: DbDep, actor: ActorDep
):
    await sharing.remove_member(db, actor, page_id, user_id, client_ip(request))


@router.post(
    "/invites",
    status_code=201,
    response_model=InviteCreatedOut,
    dependencies=[Depends(limit("manage"))],
)
async def create_invite(
    page_id: uuid.UUID, body: InviteIn, request: Request, db: DbDep, actor: VerifiedActorDep
):
    return await sharing.create_invite(
        db, actor, page_id, body.email, body.role, client_ip(request)
    )


@router.get("/invites", response_model=list[InviteOut])
async def list_invites(page_id: uuid.UUID, db: DbDep, actor: ActorDep):
    return await sharing.list_invites(db, actor, page_id)


@router.delete("/invites/{invite_id}", status_code=204)
async def revoke_invite(
    page_id: uuid.UUID, invite_id: uuid.UUID, request: Request, db: DbDep, actor: ActorDep
):
    await sharing.revoke_invite(db, actor, page_id, invite_id, client_ip(request))


@router.post(
    "/links",
    status_code=201,
    response_model=LinkCreatedOut,
    dependencies=[Depends(limit("manage"))],
)
async def create_link(
    page_id: uuid.UUID, body: LinkIn, request: Request, db: DbDep, actor: VerifiedActorDep
):
    return await sharing.create_link(
        db, actor, page_id, body.role, body.expires_in_days, client_ip(request)
    )


@router.get("/links", response_model=list[LinkOut])
async def list_links(page_id: uuid.UUID, db: DbDep, actor: ActorDep):
    return await sharing.list_links(db, actor, page_id)


@router.delete("/links/{link_id}", status_code=204)
async def revoke_link(
    page_id: uuid.UUID, link_id: uuid.UUID, request: Request, db: DbDep, actor: ActorDep
):
    await sharing.revoke_link(db, actor, page_id, link_id, client_ip(request))


# What the person who receives an invitation or a link does.
public = APIRouter(prefix="/v1", tags=["sharing"])


@public.get("/invites/{token}", response_model=InvitePreviewOut)
async def preview_invite(token: str, db: DbDep):
    return await sharing.preview_invite(db, token)


@public.post("/invites/{token}/accept", response_model=PageOut)
async def accept_invite(token: str, request: Request, db: DbDep, actor: PersonDep):
    page, _ = await sharing.accept_invite(db, actor.user, token, client_ip(request))
    return await pages.page_out(db, page, actor.user)


@public.get("/shared/{token}", response_model=SharedOut)
async def shared_page(token: str, db: DbDep):
    return await sharing.shared_page(db, token)


@public.post(
    "/shared/{token}/view-url", response_model=ViewUrlOut, dependencies=[Depends(limit("view"))]
)
async def shared_view_url(token: str, db: DbDep):
    url, expires, number = await sharing.shared_view_url(db, token)
    return ViewUrlOut(url=url, expires_at=expires, version=number)
