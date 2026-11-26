from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog


class AuditRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, action: str, user_id: int | None = None, object_type: str | None = None,
            object_id: int | None = None, ip_address: str | None = None,
            organization_id: int | None = None) -> None:
        self.session.add(AuditLog(
            user_id=user_id, action=action, object_type=object_type, object_id=object_id,
            ip_address=ip_address, organization_id=organization_id,
        ))

    def recent(self, limit: int = 20) -> list[AuditLog]:
        query = select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit)
        return list(self.session.scalars(query))
