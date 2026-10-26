import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SLUG_PATTERN = re.compile(r"^[a-z0-9]([a-z0-9-]{0,58}[a-z0-9])?$")


def clean_slug(value: str) -> str:
    value = value.strip().lower()
    if not SLUG_PATTERN.match(value):
        raise ValueError(
            "use 1 to 60 letters, numbers or dashes, not starting or ending with a dash"
        )
    return value


class PageFields(BaseModel):
    """The text fields that come with an upload."""

    title: str = Field(min_length=1, max_length=200)
    slug: str | None = None
    message: str | None = Field(default=None, max_length=500)
    entry_path: str | None = Field(default=None, max_length=200)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title cannot be empty")
        return value

    @field_validator("slug")
    @classmethod
    def _slug(cls, value: str | None) -> str | None:
        return clean_slug(value) if value else None


class VersionFields(BaseModel):
    message: str | None = Field(default=None, max_length=500)
    entry_path: str | None = Field(default=None, max_length=200)
    base_version: int | None = Field(default=None, ge=1)


class PageUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: str | None = None
    visibility: Literal["private", "members", "link"] | None = None

    @field_validator("slug")
    @classmethod
    def _slug(cls, value: str | None) -> str | None:
        return clean_slug(value) if value else None


class ViewUrlIn(BaseModel):
    version: int | None = Field(default=None, ge=1)


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    path: str
    sha256: str
    size_bytes: int
    content_type: str


class VersionOut(BaseModel):
    id: uuid.UUID
    number: int
    message: str | None
    entry_path: str
    total_bytes: int
    file_count: int
    rolled_back_from: int | None  # the version number this one restored
    author_user_id: uuid.UUID | None
    by_agent: bool  # published with an API token
    created_at: datetime


class VersionDetailOut(VersionOut):
    files: list[FileOut]


class PageOut(BaseModel):
    id: uuid.UUID
    slug: str
    title: str
    visibility: str
    owner_handle: str
    role: str  # the caller's role on this page: owner, editor, commenter or viewer
    current_version: VersionOut | None
    created_at: datetime
    updated_at: datetime


class PageListOut(BaseModel):
    items: list[PageOut]
    next_cursor: str | None


class VersionListOut(BaseModel):
    items: list[VersionOut]
    next_cursor: str | None


class PublishOut(BaseModel):
    page: PageOut
    version: VersionOut
    created: bool  # false when the files were identical to the current version


class ViewUrlOut(BaseModel):
    url: str
    expires_at: datetime
