from typing import Literal

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    client_name: str = Field(max_length=500)
    redirect_uris: list[str] = Field(max_length=50)


class RegisterOut(BaseModel):
    client_id: str
    client_name: str
    redirect_uris: list[str]
    token_endpoint_auth_method: str = "none"
    grant_types: list[str] = ["authorization_code"]
    response_types: list[str] = ["code"]


class AuthRequestIn(BaseModel):
    client_id: str = Field(max_length=200)
    redirect_uri: str = Field(max_length=1000)
    code_challenge: str = Field(default="", max_length=200)
    code_challenge_method: str = Field(default="", max_length=20)
    scope: str | None = Field(default=None, max_length=500)
    response_type: str = Field(default="", max_length=20)
    state: str | None = Field(default=None, max_length=2000)


class ApproveIn(AuthRequestIn):
    decision: Literal["allow", "deny"]


class PreviewOut(BaseModel):
    client_name: str
    redirect_host: str
    scopes: list[str]


class ApproveOut(BaseModel):
    redirect_to: str
