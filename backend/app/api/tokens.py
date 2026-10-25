import uuid

from fastapi import APIRouter, Request

from app.api.deps import DbDep, SessionActorDep, client_ip
from app.schemas.auth import TokenCreatedOut, TokenCreateIn, TokenOut
from app.services import tokens

router = APIRouter(prefix="/v1/tokens", tags=["tokens"])


@router.post("", status_code=201, response_model=TokenCreatedOut)
async def create_token(body: TokenCreateIn, request: Request, db: DbDep, actor: SessionActorDep):
    token, raw = await tokens.create(
        db,
        actor.user,
        name=body.name,
        scopes=body.scopes,
        expires_in_days=body.expires_in_days,
        ip=client_ip(request),
    )
    return TokenCreatedOut(**TokenOut.model_validate(token).model_dump(), token=raw)


@router.get("", response_model=list[TokenOut])
async def list_tokens(db: DbDep, actor: SessionActorDep):
    return await tokens.list_for_user(db, actor.user)


@router.delete("/{token_id}", status_code=204)
async def revoke_token(token_id: uuid.UUID, request: Request, db: DbDep, actor: SessionActorDep):
    await tokens.revoke(db, actor.user, token_id, client_ip(request))
