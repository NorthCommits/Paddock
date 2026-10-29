import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.policy import ALL_SCOPES

HANDLE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$")
RESERVED_HANDLES = {
    "admin", "api", "app", "www", "help", "support", "paddock", "settings",
    "login", "logout", "signup", "docs", "status", "about", "agent", "me",
}  # fmt: skip


class OnboardIn(BaseModel):
    handle: str
    display_name: str | None = Field(default=None, max_length=100)

    @field_validator("handle")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.strip().lower()


class OnboardingOut(BaseModel):
    needs_onboarding: bool
    email: str
    name: str | None
    suggestions: list[str]


class HandleCheckOut(BaseModel):
    handle: str
    available: bool
    reason: str | None


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    handle: str
    display_name: str
    created_at: datetime
    email_verified_at: datetime | None
    theme: str
    notify_requests: bool


class MeOut(BaseModel):
    user: UserOut
    scopes: list[str]


class TokenCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    scopes: list[str] = Field(min_length=1)
    expires_in_days: int | None = Field(default=None, ge=1, le=365)

    @field_validator("scopes")
    @classmethod
    def _check_scopes(cls, value: list[str]) -> list[str]:
        unknown = set(value) - ALL_SCOPES
        if unknown:
            raise ValueError(f"unknown scopes: {', '.join(sorted(unknown))}")
        return sorted(set(value))


class TokenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    prefix: str
    source: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


class TokenCreatedOut(TokenOut):
    token: str  # shown only once, at creation


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    theme: Literal["system", "light", "dark"] | None = None
    notify_requests: bool | None = None

    @field_validator("display_name")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("name cannot be empty")
        return value

    @model_validator(mode="after")
    def _something_to_change(self) -> "ProfileUpdate":
        if self.display_name is None and self.theme is None and self.notify_requests is None:
            raise ValueError("send a display_name, a theme or notify_requests")
        return self
