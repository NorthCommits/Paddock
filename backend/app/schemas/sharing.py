import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

MemberRole = Literal["viewer", "commenter", "editor"]
LinkRole = Literal["viewer", "commenter"]

# A web address in a personal message: a scheme, www, or a domain followed by a path.
_LINK = re.compile(r"https?:|www\.|[a-z0-9-]+\.[a-z]{2,}/", re.IGNORECASE)


class InviteIn(BaseModel):
    email: EmailStr
    role: MemberRole = "viewer"
    message: str | None = Field(default=None, max_length=500)  # a few warm words, emailed only

    @field_validator("email")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.lower()

    @field_validator("message")
    @classmethod
    def _message(cls, value: str | None) -> str | None:
        value = (value or "").strip()
        if not value:
            return None
        if _LINK.search(value):
            raise ValueError("A personal message cannot contain links")
        return value


class MemberUpdate(BaseModel):
    role: MemberRole


class LinkIn(BaseModel):
    role: LinkRole = "viewer"
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class MemberOut(BaseModel):
    user_id: uuid.UUID
    handle: str
    display_name: str
    email: str
    role: str
    created_at: datetime


class InviteOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime
    expires_at: datetime
    expired: bool


class InviteCreatedOut(InviteOut):
    accept_url: str  # also emailed; shown here so the owner can send it another way
    emailed: bool


class InvitePreviewOut(BaseModel):
    page_title: str
    owner_handle: str
    invited_by: str | None
    email: str
    role: str
    expires_at: datetime


class LinkOut(BaseModel):
    id: uuid.UUID
    role: str
    created_at: datetime
    expires_at: datetime | None
    expired: bool


class LinkCreatedOut(LinkOut):
    url: str  # shown once; only a hash is stored


class SharedOut(BaseModel):
    page_id: uuid.UUID
    title: str
    owner_handle: str
    role: str
    version_number: int | None
    updated_at: datetime
