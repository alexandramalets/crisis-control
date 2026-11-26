from datetime import datetime

from app.models.enums import ReportFormat, ReportStatus
from app.schemas.common import ORMModel


class ReportRead(ORMModel):
    id: int
    run_id: int
    created_by: int
    title: str
    format: ReportFormat
    status: ReportStatus
    created_at: datetime
    generated_at: datetime | None
