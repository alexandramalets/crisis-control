from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Identity, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import created_at_column, enum_type
from app.models.enums import ReportFormat, ReportStatus


class Report(Base):
    """Отчёт по результатам исследования. Содержимое появляется после формирования."""

    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint(
            "(status = 'ready') = (content IS NOT NULL AND generated_at IS NOT NULL)",
            name="content_iff_ready",
        ),
        CheckConstraint("length(btrim(title)) > 0", name="title_not_blank"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    format: Mapped[ReportFormat] = mapped_column(enum_type(ReportFormat, "format"))
    status: Mapped[ReportStatus] = mapped_column(enum_type(ReportStatus, "status"), default=ReportStatus.PENDING)
    created_at: Mapped[datetime] = created_at_column()
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
