import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select

from app.api.deps import ActorDep, DbDep, client_ip
from app.core.errors import AppError
from app.core.ratelimit import limit
from app.db.models import Event, Webhook, WebhookDelivery
from app.schemas.webhooks import (
    DeliveryList,
    DeliveryOut,
    WebhookCreated,
    WebhookEdit,
    WebhookIn,
    WebhookOut,
)
from app.services import webhooks

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


def _need_scope(actor) -> None:
    if "events:read" not in actor.scopes:
        raise AppError(403, "forbidden", "This token lacks the events:read scope")


def _out(hook: Webhook) -> dict:
    return {
        "id": str(hook.id),
        "url": hook.url,
        "event_types": hook.event_types,
        "active": hook.active,
        "created_at": hook.created_at,
    }


@router.post(
    "", status_code=201, response_model=WebhookCreated, dependencies=[Depends(limit("manage"))]
)
async def create(body: WebhookIn, request: Request, db: DbDep, actor: ActorDep):
    _need_scope(actor)
    hook, secret = await webhooks.create(
        db, actor, url=body.url, event_types=body.event_types, ip=client_ip(request)
    )
    return {**_out(hook), "secret": secret}


@router.get("", response_model=list[WebhookOut])
async def list_all(db: DbDep, actor: ActorDep):
    _need_scope(actor)
    rows = await db.scalars(
        select(Webhook).where(Webhook.user_id == actor.user.id).order_by(Webhook.created_at)
    )
    return [_out(h) for h in rows]


@router.patch("/{hook_id}", response_model=WebhookOut)
async def edit(hook_id: uuid.UUID, body: WebhookEdit, db: DbDep, actor: ActorDep):
    _need_scope(actor)
    hook = await webhooks.mine(db, actor, hook_id)
    if body.active is not None:
        hook.active = body.active
    if body.event_types is not None:
        hook.event_types = sorted(set(body.event_types))
    await db.commit()
    return _out(hook)


@router.delete("/{hook_id}", status_code=204)
async def remove(hook_id: uuid.UUID, request: Request, db: DbDep, actor: ActorDep):
    _need_scope(actor)
    await webhooks.remove(db, actor, hook_id, client_ip(request))


@router.post("/{hook_id}/test", response_model=DeliveryOut, dependencies=[Depends(limit("manage"))])
async def test(hook_id: uuid.UUID, db: DbDep, actor: ActorDep):
    _need_scope(actor)
    delivery = await webhooks.send_test(db, actor, hook_id)
    return {**_delivery(delivery), "event_type": "webhook.test"}


def _delivery(d: WebhookDelivery) -> dict:
    return {
        "id": str(d.id),
        "event_id": d.event_id,
        "status": d.status,
        "attempts": d.attempts,
        "next_attempt_at": d.next_attempt_at,
        "last_status_code": d.last_status_code,
        "last_error": d.last_error,
        "created_at": d.created_at,
    }


@router.get("/{hook_id}/deliveries", response_model=DeliveryList)
async def deliveries(
    hook_id: uuid.UUID, db: DbDep, actor: ActorDep, limit: int = Query(20, ge=1, le=100)
):
    _need_scope(actor)
    hook = await webhooks.mine(db, actor, hook_id)
    rows = await db.execute(
        select(WebhookDelivery, Event.type)
        .join(Event, Event.id == WebhookDelivery.event_id)
        .where(WebhookDelivery.webhook_id == hook.id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
    )
    return {"items": [{**_delivery(d), "event_type": t} for d, t in rows]}
