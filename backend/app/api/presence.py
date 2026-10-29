import uuid

from fastapi import APIRouter, Response

from app.api.deps import DbDep, PersonDep, VerifiedPersonDep
from app.schemas.presence import PeopleOut
from app.services import pages, presence

router = APIRouter(tags=["presence"])


@router.post("/v1/pages/{page_id}/presence", status_code=204)
async def heartbeat(page_id: uuid.UUID, db: DbDep, actor: VerifiedPersonDep):
    page = await pages.get_for_actor(db, actor, page_id, "page.view")
    await presence.heartbeat(db, page, actor.user)
    return Response(status_code=204)


@router.delete("/v1/pages/{page_id}/presence", status_code=204)
async def leave(page_id: uuid.UUID, db: DbDep, actor: VerifiedPersonDep):
    page = await pages.get_for_actor(db, actor, page_id, "page.view")
    await presence.leave(db, page, actor.user)
    return Response(status_code=204)


@router.get("/v1/pages/{page_id}/people", response_model=PeopleOut)
async def people(page_id: uuid.UUID, db: DbDep, actor: PersonDep):
    page = await pages.get_for_actor(db, actor, page_id, "page.view")
    return PeopleOut(items=await presence.people(db, page))
