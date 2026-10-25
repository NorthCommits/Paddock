import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.session import get_session

router = APIRouter(tags=["operations"])


@router.get("/healthz")
async def healthz() -> dict:
    """The process is alive. Does not touch the database."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(session: Annotated[AsyncSession, Depends(get_session)]) -> dict:
    """The database is reachable. The wait is generous because Neon may be waking up."""
    try:
        await asyncio.wait_for(session.execute(text("select 1")), timeout=15)
    except Exception as exc:
        raise AppError(503, "database_unavailable", "Database is not reachable") from exc
    return {"status": "ready"}
