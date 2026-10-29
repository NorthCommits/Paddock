import json
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

MAX_BODY = 5000
MAX_ANCHOR_BYTES = 4096


def _clean_body(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("cannot be empty")
    return value


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_BODY)
    parent_id: uuid.UUID | None = None
    version: int | None = Field(default=None, ge=1)
    anchor: dict | None = None

    _body = field_validator("body")(_clean_body)

    @field_validator("anchor")
    @classmethod
    def _anchor_size(cls, value: dict | None) -> dict | None:
        if value is not None and len(json.dumps(value)) > MAX_ANCHOR_BYTES:
            raise ValueError(f"must be under {MAX_ANCHOR_BYTES} bytes")
        return value


class CommentEdit(BaseModel):
    body: str = Field(min_length=1, max_length=MAX_BODY)

    _body = field_validator("body")(_clean_body)


class ResolveIn(BaseModel):
    resolved: bool = True


class ClaimIn(BaseModel):
    minutes: int = Field(default=10, ge=1, le=60)


class CompleteIn(BaseModel):
    result_version: int = Field(ge=1)
    reply: str | None = Field(default=None, max_length=MAX_BODY)


class DismissIn(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class AuthorOut(BaseModel):
    user_id: uuid.UUID | None
    handle: str | None
    display_name: str | None
    by_agent: bool
    # For an agent: who it belongs to and which app it is, such as "Swapnil's Claude".
    agent_label: str | None = None


class RequestOut(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    comment_id: uuid.UUID
    status: Literal["open", "claimed", "done", "dismissed"]
    base_version: int | None
    result_version: int | None
    claim_expires_at: datetime | None
    dismiss_reason: str | None
    created_at: datetime
    updated_at: datetime


class CommentOut(BaseModel):
    id: uuid.UUID
    page_id: uuid.UUID
    parent_id: uuid.UUID | None
    version_number: int | None
    author: AuthorOut
    body: str
    anchor: dict | None
    mentions_agent: bool
    created_at: datetime
    edited_at: datetime | None
    deleted: bool
    resolved_at: datetime | None
    resolved_by: str | None  # handle of the person who resolved the thread
    request: RequestOut | None
    replies: list["CommentOut"] = []


class CommentListOut(BaseModel):
    items: list[CommentOut]


class RequestComment(BaseModel):
    id: uuid.UUID
    thread_id: uuid.UUID
    body: str
    author: AuthorOut
    version_number: int | None
    anchor: dict | None


class RequestItemOut(RequestOut):
    """A request with what an agent needs to act: the page and the comment."""

    page_title: str
    page_slug: str
    owner_handle: str
    comment: RequestComment


class RequestListOut(BaseModel):
    items: list[RequestItemOut]
