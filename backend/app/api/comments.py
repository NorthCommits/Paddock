import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response

from app.api.deps import ActorDep, DbDep, client_ip
from app.core.ratelimit import limit
from app.schemas.comments import (
    ClaimIn,
    CommentEdit,
    CommentIn,
    CommentListOut,
    CommentOut,
    CompleteIn,
    DismissIn,
    RequestItemOut,
    RequestListOut,
    ResolveIn,
)
from app.services import comments, requests

router = APIRouter(tags=["comments"])


@router.get("/v1/pages/{page_id}/comments", response_model=CommentListOut)
async def list_comments(
    page_id: uuid.UUID,
    db: DbDep,
    actor: ActorDep,
    status: Literal["open", "resolved"] | None = None,
):
    return await comments.list_for_page(db, actor, page_id, status)


@router.post(
    "/v1/pages/{page_id}/comments",
    status_code=201,
    response_model=CommentOut,
    dependencies=[Depends(limit("comment"))],
)
async def create_comment(
    page_id: uuid.UUID, body: CommentIn, request: Request, db: DbDep, actor: ActorDep
):
    return await comments.create(
        db,
        actor,
        page_id,
        body=body.body,
        parent_id=body.parent_id,
        version=body.version,
        anchor=body.anchor,
        ip=client_ip(request),
    )


@router.patch(
    "/v1/comments/{comment_id}", response_model=CommentOut, dependencies=[Depends(limit("comment"))]
)
async def edit_comment(
    comment_id: uuid.UUID, body: CommentEdit, request: Request, db: DbDep, actor: ActorDep
):
    return await comments.edit(db, actor, comment_id, body=body.body, ip=client_ip(request))


@router.delete(
    "/v1/comments/{comment_id}", status_code=204, dependencies=[Depends(limit("comment"))]
)
async def delete_comment(comment_id: uuid.UUID, request: Request, db: DbDep, actor: ActorDep):
    await comments.delete(db, actor, comment_id, ip=client_ip(request))
    return Response(status_code=204)


@router.post(
    "/v1/comments/{comment_id}/resolve",
    response_model=CommentOut,
    dependencies=[Depends(limit("comment"))],
)
async def resolve_comment(
    comment_id: uuid.UUID,
    request: Request,
    db: DbDep,
    actor: ActorDep,
    body: ResolveIn | None = None,
):
    resolved = body.resolved if body else True
    return await comments.resolve(db, actor, comment_id, resolved=resolved, ip=client_ip(request))


@router.get("/v1/requests", response_model=RequestListOut)
async def list_requests(
    db: DbDep,
    actor: ActorDep,
    status: Literal["open", "claimed", "done", "dismissed"] | None = None,
    page_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return await requests.list_requests(db, actor, status=status, page_id=page_id, limit=limit)


@router.post(
    "/v1/requests/{request_id}/claim",
    response_model=RequestItemOut,
    dependencies=[Depends(limit("request"))],
)
async def claim_request(
    request_id: uuid.UUID,
    request: Request,
    db: DbDep,
    actor: ActorDep,
    body: ClaimIn | None = None,
):
    minutes = body.minutes if body else 10
    return await requests.claim(db, actor, request_id, minutes=minutes, ip=client_ip(request))


@router.post(
    "/v1/requests/{request_id}/complete",
    response_model=RequestItemOut,
    dependencies=[Depends(limit("request"))],
)
async def complete_request(
    request_id: uuid.UUID, body: CompleteIn, request: Request, db: DbDep, actor: ActorDep
):
    return await requests.complete(
        db,
        actor,
        request_id,
        result_version=body.result_version,
        reply=body.reply,
        ip=client_ip(request),
    )


@router.post(
    "/v1/requests/{request_id}/dismiss",
    response_model=RequestItemOut,
    dependencies=[Depends(limit("request"))],
)
async def dismiss_request(
    request_id: uuid.UUID,
    request: Request,
    db: DbDep,
    actor: ActorDep,
    body: DismissIn | None = None,
):
    reason = body.reason if body else None
    return await requests.dismiss(db, actor, request_id, reason=reason, ip=client_ip(request))
