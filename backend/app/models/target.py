from datetime import date
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Identity, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import AMOUNT, enum_type
from app.models.enums import TargetKind


class IndicatorTarget(Base):
    """Плановое, нормативное или целевое значение показателя (ПЗ, табл. 1.4).

    period_id IS NULL — значение действует для всех периодов.
    """

    __tablename__ = "indicator_targets"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "indicator_id", "period_id", "kind",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id", ondelete="RESTRICT"), index=True)
    period_id: Mapped[int | None] = mapped_column(ForeignKey("periods.id", ondelete="RESTRICT"), index=True)
    kind: Mapped[TargetKind] = mapped_column(enum_type(TargetKind, "kind"))
    value: Mapped[Decimal] = mapped_column(AMOUNT)
    source: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)


class IndicatorThreshold(Base):
    """Пороговые значения показателя для организации (ПЗ, табл. 1.4)."""

    __tablename__ = "indicator_thresholds"
    __table_args__ = (
        CheckConstraint("lower_bound IS NOT NULL OR upper_bound IS NOT NULL", name="has_bound"),
        CheckConstraint(
            "lower_bound IS NULL OR upper_bound IS NULL OR lower_bound <= upper_bound",
            name="bounds_ordered",
        ),
    )

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True,
    )
    indicator_id: Mapped[int] = mapped_column(
        ForeignKey("indicators.id", ondelete="RESTRICT"), primary_key=True, index=True,
    )
    lower_bound: Mapped[Decimal | None] = mapped_column(AMOUNT)
    upper_bound: Mapped[Decimal | None] = mapped_column(AMOUNT)
    source: Mapped[str | None] = mapped_column(String(300))
    notes: Mapped[str | None] = mapped_column(Text)
    methodology: Mapped[str | None] = mapped_column(Text)
