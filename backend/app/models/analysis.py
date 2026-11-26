from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Identity, Integer, SmallInteger, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import PARAMETER_NUMBER, WEIGHT, created_at_column, enum_type
from app.models.enums import AnalysisStatus, ProcedureStatus, ProcedureType


class AnalysisRun(Base):
    """Аналитическое исследование: один запуск анализа набора данных (UC-3)."""

    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint("random_state >= 0", name="random_state_non_negative"),
        CheckConstraint("finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
                        name="finished_after_start"),
        CheckConstraint("parent_run_id IS NULL OR parent_run_id <> id", name="parent_not_self"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    parent_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL"), index=True,
    )
    period_from_id: Mapped[int] = mapped_column(ForeignKey("periods.id", ondelete="RESTRICT"), index=True)
    period_to_id: Mapped[int] = mapped_column(ForeignKey("periods.id", ondelete="RESTRICT"), index=True)
    status: Mapped[AnalysisStatus] = mapped_column(
        enum_type(AnalysisStatus, "status"), default=AnalysisStatus.QUEUED,
    )
    random_state: Mapped[int] = mapped_column(Integer)
    analytics_service_version: Mapped[str | None] = mapped_column(String(32))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    indicators: Mapped[list["AnalysisRunIndicator"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True,
    )
    procedures: Mapped[list["AnalysisProcedure"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, order_by="AnalysisProcedure.id",
    )


class AnalysisRunIndicator(Base):
    """Показатель, включённый в исследование, и его вес w_j (формула 7)."""

    __tablename__ = "analysis_run_indicators"
    __table_args__ = (
        CheckConstraint("weight >= 0 AND weight <= 1", name="weight_range"),
    )

    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), primary_key=True)
    indicator_id: Mapped[int] = mapped_column(
        ForeignKey("indicators.id", ondelete="RESTRICT"), primary_key=True, index=True,
    )
    weight: Mapped[Decimal] = mapped_column(WEIGHT)


class AnalysisProcedure(Base):
    """Аналитическая процедура в составе исследования; заголовок её результатов (BR-4, REL-1)."""

    __tablename__ = "analysis_procedures"
    __table_args__ = (
        UniqueConstraint("run_id", "procedure_type"),
        CheckConstraint("finished_at IS NULL OR started_at IS NULL OR finished_at >= started_at",
                        name="finished_after_start"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    procedure_type: Mapped[ProcedureType] = mapped_column(enum_type(ProcedureType, "procedure_type"))
    method: Mapped[str] = mapped_column(String(50))
    status: Mapped[ProcedureStatus] = mapped_column(
        enum_type(ProcedureStatus, "status"), default=ProcedureStatus.PENDING,
    )
    message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    parameters: Mapped[list["AnalysisParameter"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True,
        order_by=lambda: [AnalysisParameter.name, AnalysisParameter.position],
    )


class AnalysisParameter(Base):
    """Параметр процедуры (REP-2, EXT-2). Ровно одно из значений задано.

    position > 0 используется для списочных параметров (например, набор моделей прогноза).
    """

    __tablename__ = "analysis_parameters"
    __table_args__ = (
        CheckConstraint("num_nonnulls(numeric_value, text_value, boolean_value) = 1", name="single_value"),
        CheckConstraint("position >= 0", name="position_non_negative"),
        CheckConstraint("name ~ '^[a-z][a-z0-9_]{0,63}$'", name="name_format"),
    )

    procedure_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_procedures.id", ondelete="CASCADE"), primary_key=True,
    )
    name: Mapped[str] = mapped_column(String(64), primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True, default=0)
    numeric_value: Mapped[Decimal | None] = mapped_column(PARAMETER_NUMBER)
    text_value: Mapped[str | None] = mapped_column(String(200))
    boolean_value: Mapped[bool | None] = mapped_column(Boolean)
