import uuid

from pydantic import BaseModel


class PersonOut(BaseModel):
    id: uuid.UUID
    handle: str
    display_name: str
    here: bool


class PeopleOut(BaseModel):
    items: list[PersonOut]
