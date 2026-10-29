import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationPage(BaseModel):
    id: uuid.UUID
    title: str


class NotificationRequest(BaseModel):
    id: uuid.UUID
    status: str
    my_offer: str | None  # offered, declined, won or lost, for this person
    approved_by: str | None
    approved_by_me: bool


class NotificationItem(BaseModel):
    id: uuid.UUID
    kind: str
    created_at: datetime
    read: bool
    body: str
    actor: str | None
    page: NotificationPage | None
    request: NotificationRequest | None


class AgentPresence(BaseModel):
    connected: bool
    active: bool
    last_seen_at: datetime | None


class NotificationList(BaseModel):
    items: list[NotificationItem]
    unread: int
    agent: AgentPresence
