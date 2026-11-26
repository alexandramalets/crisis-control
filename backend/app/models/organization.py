from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, Identity, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import created_at_column
from app.models.enums import OrganizationAccessLevel


class OrganizationAccess(Base):
    """Назначение сотруднику доступа к организации. Владелец также получает запись при создании."""

    __tablename__ = "organization_access"
    __table_args__ = (
        Index("ix_organization_access_user_id", "user_id"),
        CheckConstraint("access_level IN ('view', 'edit')", name="ck_organization_access_level"),
    )

    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    granted_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    granted_at: Mapped[datetime] = created_at_column()
    access_level: Mapped[str] = mapped_column(
        String(16),
        default=OrganizationAccessLevel.VIEW.value,
        server_default=OrganizationAccessLevel.VIEW.value,
    )


class Organization(Base):
    """Объект управления, данные которого анализируются (ПЗ, с. 10)."""

    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("owner_id", "name"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_column()


class Category(Base):
    """Измерение «категория / подразделение» многомерных данных (ПЗ, табл. 1.4, C)."""

    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("organization_id", "name"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
