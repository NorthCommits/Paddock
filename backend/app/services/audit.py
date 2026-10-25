import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog


def record(
    db: AsyncSession,
    *,
    action: str,
    user_id: uuid.UUID | None = None,
    token_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    ip: str | None = None,
    meta: dict | None = None,
) -> None:
    """Add an audit row to the current transaction. The caller commits."""
    db.add(
        AuditLog(
            action=action,
            user_id=user_id,
            token_id=token_id,
            target_type=target_type,
            target_id=target_id,
            ip=ip,
            meta=meta,
        )
    )
