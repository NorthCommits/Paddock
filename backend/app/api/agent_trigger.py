from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.deps import DbDep, VerifiedPersonDep, client_ip
from app.core.ratelimit import limit
from app.services import triggers

router = APIRouter(prefix="/v1/me/agent-trigger", tags=["agent trigger"])


class TriggerIn(BaseModel):
    url: str = Field(max_length=300)
    token: str = Field(min_length=1, max_length=500)


class TriggerOut(BaseModel):
    saved: bool
    last_fired_at: datetime | None = None
    last_result: str | None = None


class TestOut(BaseModel):
    result: str


async def _out(db, user) -> TriggerOut:
    row = await triggers.get(db, user.id)
    if row is None:
        return TriggerOut(saved=False)
    return TriggerOut(saved=True, last_fired_at=row.last_fired_at, last_result=row.last_result)


@router.get("", response_model=TriggerOut)
async def get_trigger(db: DbDep, actor: VerifiedPersonDep):
    return await _out(db, actor.user)


@router.put("", response_model=TriggerOut, dependencies=[Depends(limit("manage"))])
async def save_trigger(body: TriggerIn, request: Request, db: DbDep, actor: VerifiedPersonDep):
    await triggers.save(db, actor.user.id, body.url, body.token, client_ip(request))
    return await _out(db, actor.user)


@router.delete("", status_code=204)
async def remove_trigger(request: Request, db: DbDep, actor: VerifiedPersonDep):
    await triggers.remove(db, actor.user.id, client_ip(request))


@router.post("/test", response_model=TestOut, dependencies=[Depends(limit("manage"))])
async def test_trigger(db: DbDep, actor: VerifiedPersonDep):
    return TestOut(result=await triggers.test_fire(db, actor.user.id))
