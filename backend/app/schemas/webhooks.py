from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.services.events import EVENT_TYPES


class WebhookIn(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    event_types: list[str] = Field(default_factory=list)  # empty means every event

    @field_validator("event_types")
    @classmethod
    def known(cls, values: list[str]) -> list[str]:
        unknown = [v for v in values if v not in EVENT_TYPES]
        if unknown:
            raise ValueError(f"Unknown event type: {unknown[0]}")
        return values


class WebhookEdit(BaseModel):
    active: bool | None = None
    event_types: list[str] | None = None

    @field_validator("event_types")
    @classmethod
    def known(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return WebhookIn.known(values)


class WebhookOut(BaseModel):
    id: str
    url: str
    event_types: list[str]
    active: bool
    created_at: datetime


class WebhookCreated(WebhookOut):
    secret: str  # shown once


class DeliveryOut(BaseModel):
    id: str
    event_id: int
    event_type: str
    status: str
    attempts: int
    next_attempt_at: datetime | None
    last_status_code: int | None
    last_error: str | None
    created_at: datetime


class DeliveryList(BaseModel):
    items: list[DeliveryOut]
