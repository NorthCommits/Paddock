import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

MAX_LENGTH = 1000


class MessageIn(BaseModel):
    body: str
    to: uuid.UUID | None = None

    @field_validator("body")
    @classmethod
    def clean(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Write something to send")
        if len(value) > MAX_LENGTH:
            raise ValueError(f"A message can be at most {MAX_LENGTH} characters")
        return value


class Sender(BaseModel):
    id: uuid.UUID
    handle: str
    display_name: str


class SeenBy(BaseModel):
    id: uuid.UUID
    name: str
    at: datetime


class ReadIn(BaseModel):
    """Everything up to and including this message has been read."""

    up_to: uuid.UUID
    with_id: uuid.UUID | None = Field(default=None, alias="with")


class MessageOut(BaseModel):
    id: uuid.UUID
    sender: Sender
    to: uuid.UUID | None
    body: str
    created_at: datetime
    deleted: bool
    # Only filled in for your own messages: who has read it, and how many people could.
    seen_by: list[SeenBy] = []
    audience: int = 0


class MessageListOut(BaseModel):
    items: list[MessageOut]
    more: bool
