from typing import Literal

from pydantic import BaseModel, Field

# A block id is a short label made by the page helper: letters, digits, dash and underscore.
BLOCK = r"^[A-Za-z0-9_-]{1,64}$"
ReactionKey = Literal["like", "love", "cheer", "eyes"]


class FocusIn(BaseModel):
    block: str | None = Field(default=None, pattern=BLOCK)
    kind: Literal["look", "select"] = "look"


class ReactionIn(BaseModel):
    block: str = Field(pattern=BLOCK)
    key: ReactionKey
    on: bool = True


class ReactionOut(BaseModel):
    block: str
    key: str
    count: int
    mine: bool
    who: list[str]


class ReactionListOut(BaseModel):
    items: list[ReactionOut]
