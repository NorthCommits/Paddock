import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.policy import ALL_SCOPES

HANDLE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{1,28}[a-z0-9]$")
RESERVED_HANDLES = {
    "admin", "api", "app", "www", "help", "support", "paddock", "settings",
    "login", "logout", "signup", "docs", "status", "about", "agent", "me",
}  # fmt: skip


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    handle: str
    display_name: str | None = Field(default=None, max_length=100)

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("handle")
    @classmethod
    def _check_handle(cls, value: str) -> str:
        value = value.lower()
        if not HANDLE_PATTERN.match(value):
            raise ValueError(
                "use 3 to 30 letters, numbers or dashes, not starting or ending with a dash"
            )
        if value in RESERVED_HANDLES:
            raise ValueError("this handle is reserved")
        return value


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    handle: str
    display_name: str
    created_at: datetime
    email_verified_at: datetime | None


class SessionOut(BaseModel):
    user: UserOut
    csrf_token: str


class MeOut(BaseModel):
    user: UserOut
    scopes: list[str]
    csrf_token: str | None  # only for browser sessions


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
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    expires_at: datetime | None
    revoked_at: datetime | None


class TokenCreatedOut(TokenOut):
    token: str  # shown only once, at creation


class ProfileUpdate(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be empty")
        return value


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class BrowserSessionOut(BaseModel):
    id: uuid.UUID
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str | None
    ip: str | None
    current: bool


class VerifyEmailIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class ForgotPasswordIn(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def _lower_email(cls, value: str) -> str:
        return value.lower()


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=10, max_length=128)
