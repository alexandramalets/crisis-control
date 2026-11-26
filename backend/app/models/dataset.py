from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, CheckConstraint, ForeignKey, Identity, Index, Integer, LargeBinary, SmallInteger,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import AMOUNT, created_at_column, enum_type
from app.models.enums import IssueSeverity, PeriodGranularity


class Dataset(Base):
    """Загруженный и прошедший проверку структуры набор многомерных данных (BR-1, SEC-2)."""

    __tablename__ = "datasets"
    __table_args__ = (
        UniqueConstraint("organization_id", "name", "version_no", name="uq_datasets_org_name_version"),
        CheckConstraint("source_sha256 ~ '^[0-9a-f]{64}$'", name="source_sha256_format"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    # NULL — значения переданы через API без файла; SHA-256 тогда считается
    # от канонического представления значений
    source_filename: Mapped[str | None] = mapped_column(String(255))
    source_sha256: Mapped[str] = mapped_column(String(64))
    granularity: Mapped[PeriodGranularity] = mapped_column(enum_type(PeriodGranularity, "granularity"))
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    predecessor_id: Mapped[int | None] = mapped_column(ForeignKey("datasets.id", ondelete="SET NULL"))
    notes: Mapped[str | None] = mapped_column(Text)
    quality_status: Mapped[str] = mapped_column(String(32), default="ready")
    created_at: Mapped[datetime] = created_at_column()


class DatasetFile(Base):
    """Исходный файл в зашифрованном виде (AES-256-GCM, ЛЗ п. 3.4.1). Копия также лежит в DATA_DIR."""

    __tablename__ = "dataset_files"
    __table_args__ = (
        CheckConstraint("octet_length(nonce) = 12", name="nonce_length"),
        CheckConstraint("key_version > 0", name="key_version_positive"),
    )

    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), primary_key=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    nonce: Mapped[bytes] = mapped_column(LargeBinary)
    key_version: Mapped[int] = mapped_column(SmallInteger)


class DatasetIssue(Base):
    """Замечание проверки загруженного файла (BR-8, UI-3)."""

    __tablename__ = "dataset_issues"
    __table_args__ = (
        CheckConstraint("row_number IS NULL OR row_number >= 1", name="row_number_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    severity: Mapped[IssueSeverity] = mapped_column(enum_type(IssueSeverity, "severity"))
    code: Mapped[str] = mapped_column(String(50))
    row_number: Mapped[int | None] = mapped_column(Integer)
    column_name: Mapped[str | None] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)


class IndicatorValue(Base):
    """Значение показателя: «длинный» формат (набор × показатель × период × категория).

    value IS NULL — пропуск в исходном файле; фиксируется, чтобы предобработка была
    воспроизводимой и объяснимой (INT-2).
    """

    __tablename__ = "indicator_values"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "indicator_id", "period_id", "category_id",
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_indicator_values_indicator_id", "indicator_id"),
        Index("ix_indicator_values_period_id", "period_id"),
        Index("ix_indicator_values_category_id", "category_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"))
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id", ondelete="RESTRICT"))
    period_id: Mapped[int] = mapped_column(ForeignKey("periods.id", ondelete="RESTRICT"))
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    value: Mapped[Decimal | None] = mapped_column(AMOUNT)
