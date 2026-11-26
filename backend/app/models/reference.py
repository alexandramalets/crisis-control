from datetime import date

from sqlalchemy import (
    CheckConstraint, Date, ForeignKey, Identity, Integer, SmallInteger, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import enum_type
from app.models.enums import ImpactDirection, PeriodGranularity


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    symbol: Mapped[str] = mapped_column(String(16))


class IndicatorGroup(Base):
    """Тип показателя: финансовый, операционный."""

    __tablename__ = "indicator_groups"

    id: Mapped[int] = mapped_column(SmallInteger, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(100))


class Indicator(Base):
    """Описание показателя. owner_id IS NULL — системный показатель из справочника."""

    __tablename__ = "indicators"
    __table_args__ = (
        UniqueConstraint("owner_id", "code", postgresql_nulls_not_distinct=True),
        CheckConstraint("code ~ '^[a-z][a-z0-9_]{0,49}$'", name="code_format"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id", ondelete="RESTRICT"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("indicator_groups.id", ondelete="RESTRICT"), index=True)
    impact_direction: Mapped[ImpactDirection] = mapped_column(enum_type(ImpactDirection, "impact_direction"))
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    description: Mapped[str | None] = mapped_column(Text)

    unit: Mapped[Unit] = relationship(lazy="joined")
    group: Mapped[IndicatorGroup] = relationship(lazy="joined")


class Period(Base):
    """Временной интервал наблюдения. Общий справочник для всех наборов данных."""

    __tablename__ = "periods"
    __table_args__ = (
        UniqueConstraint("granularity", "start_date"),
        CheckConstraint("end_date >= start_date", name="end_not_before_start"),
        CheckConstraint("extract(day from start_date) = 1", name="starts_on_first_day"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    granularity: Mapped[PeriodGranularity] = mapped_column(enum_type(PeriodGranularity, "granularity"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
