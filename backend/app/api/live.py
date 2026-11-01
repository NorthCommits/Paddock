import uuid

from fastapi import APIRouter, Depends, Response

from app.api.deps import DbDep, PersonDep, VerifiedPersonDep
from app.core.ratelimit import limit
from app.schemas.live import FocusIn, ReactionIn, ReactionListOut
from app.services import pages, presence, reactions

router = APIRouter(tags=["live"])


@router.post("/v1/pages/{page_id}/focus", status_code=204, dependencies=[Depends(limit("focus"))])
async def focus(page_id: uuid.UUID, body: FocusIn, db: DbDep, actor: VerifiedPersonDep):
    page = await pages.get_for_actor(db, actor, page_id, "page.view")
    presence.focus(page, actor.user, body.block, body.kind)
    return Response(status_code=204)


@router.get("/v1/pages/{page_id}/reactions", response_model=ReactionListOut)
async def list_reactions(page_id: uuid.UUID, db: DbDep, actor: PersonDep):
    page = await pages.get_for_actor(db, actor, page_id, "page.view")
    return ReactionListOut(items=await reactions.list_for_page(db, page, actor.user))


@router.put(
    "/v1/pages/{page_id}/reactions", status_code=204, dependencies=[Depends(limit("react"))]
)
async def set_reaction(page_id: uuid.UUID, body: ReactionIn, db: DbDep, actor: VerifiedPersonDep):
    page = await pages.get_for_actor(db, actor, page_id, "comment.create")
    await reactions.set_reaction(db, page, actor.user, body.block, body.key, body.on)
    return Response(status_code=204)
