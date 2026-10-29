from fastapi import APIRouter

from app.api.deps import DbDep, PersonDep
from app.schemas.notifications import NotificationList
from app.services import notifications

router = APIRouter(prefix="/v1/notifications", tags=["notifications"])


@router.get("", response_model=NotificationList)
async def list_notifications(db: DbDep, actor: PersonDep):
    return await notifications.list_for(db, actor.user)


@router.post("/read", status_code=204)
async def read_all(db: DbDep, actor: PersonDep):
    await notifications.mark_all_read(db, actor.user)
