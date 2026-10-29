import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

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


class MessageOut(BaseModel):
    id: uuid.UUID
    sender: Sender
    to: uuid.UUID | None
    body: str
    created_at: datetime
    deleted: bool


class MessageListOut(BaseModel):
    items: list[MessageOut]
    more: bool
