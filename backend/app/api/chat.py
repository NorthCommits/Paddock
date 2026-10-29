import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import DbDep, PersonDep, VerifiedPersonDep
from app.core.ratelimit import limit
from app.schemas.chat import MessageIn, MessageListOut, MessageOut
from app.services import chat, pages

router = APIRouter(tags=["chat"])


@router.get("/v1/pages/{page_id}/messages", response_model=MessageListOut)
async def list_messages(
    page_id: uuid.UUID,
    db: DbDep,
    actor: PersonDep,
    with_id: Annotated[uuid.UUID | None, Query(alias="with")] = None,
    before: uuid.UUID | None = None,
):
    page = await pages.get_for_actor(db, actor, page_id, "page.view")
    items, more = await chat.list_messages(db, page, actor.user, with_id, before)
    return MessageListOut(items=items, more=more)


@router.post(
    "/v1/pages/{page_id}/messages",
    status_code=201,
    response_model=MessageOut,
    dependencies=[Depends(limit("chat"))],
)
async def send_message(page_id: uuid.UUID, body: MessageIn, db: DbDep, actor: VerifiedPersonDep):
    page = await pages.get_for_actor(db, actor, page_id, "chat.write")
    return await chat.send(db, page, actor.user, body.body, body.to)


@router.delete("/v1/messages/{message_id}", status_code=204)
async def delete_message(message_id: uuid.UUID, db: DbDep, actor: VerifiedPersonDep):
    await chat.delete(db, actor, message_id)
    return Response(status_code=204)
