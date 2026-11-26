"""Начальное заполнение справочников: роли, единицы измерения, группы, системные показатели.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22 23:00:00

Системные показатели — перечень из пояснительной записки; коды совпадают с заголовками
столбцов шаблона загрузки (sample-data/demo_indicators.csv).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, Sequence[str], None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLES = [
    ("analyst", "Аналитик"),
    ("admin", "Администратор"),
]

UNITS = [
    ("RUB", "Российский рубль", "руб."),
    ("PCS", "Штука", "шт."),
    ("PCT", "Процент", "%"),
]

GROUPS = [
    ("financial", "Финансовые показатели"),
    ("operational", "Операционные показатели"),
]

# код, наименование, единица, группа, направление влияния на состояние организации
INDICATORS = [
    ("revenue", "Выручка", "RUB", "financial", "higher_better"),
    ("sales_volume", "Объём продаж", "PCS", "operational", "higher_better"),
    ("profit", "Прибыль", "RUB", "financial", "higher_better"),
    ("receivables", "Дебиторская задолженность", "RUB", "financial", "lower_better"),
    ("payables", "Кредиторская задолженность", "RUB", "financial", "lower_better"),
    ("inventory", "Запасы", "RUB", "operational", "neutral"),
    ("cash", "Денежные средства", "RUB", "financial", "higher_better"),
    ("cf_operating", "Денежный поток от операционной деятельности", "RUB", "financial", "higher_better"),
    ("cf_investing", "Денежный поток от инвестиционной деятельности", "RUB", "financial", "neutral"),
    ("cf_financing", "Денежный поток от финансовой деятельности", "RUB", "financial", "neutral"),
]

roles = sa.table("roles", sa.column("code"), sa.column("name"))
units = sa.table("units", sa.column("code"), sa.column("name"), sa.column("symbol"))
groups = sa.table("indicator_groups", sa.column("code"), sa.column("name"))


def upgrade() -> None:
    op.bulk_insert(roles, [{"code": c, "name": n} for c, n in ROLES])
    op.bulk_insert(units, [{"code": c, "name": n, "symbol": s} for c, n, s in UNITS])
    op.bulk_insert(groups, [{"code": c, "name": n} for c, n in GROUPS])

    insert_indicator = sa.text(
        "INSERT INTO indicators (code, name, unit_id, group_id, impact_direction) "
        "SELECT :code, :name, u.id, g.id, :direction "
        "FROM units u, indicator_groups g WHERE u.code = :unit AND g.code = :group"
    )
    for code, name, unit, group, direction in INDICATORS:
        op.execute(insert_indicator.bindparams(code=code, name=name, unit=unit, group=group, direction=direction))


def downgrade() -> None:
    codes = [code for code, *_ in INDICATORS]
    op.execute(sa.text("DELETE FROM indicators WHERE owner_id IS NULL AND code = ANY(:codes)").bindparams(codes=codes))
    op.execute(sa.text("DELETE FROM indicator_groups WHERE code = ANY(:codes)").bindparams(
        codes=[c for c, _ in GROUPS]))
    op.execute(sa.text("DELETE FROM units WHERE code = ANY(:codes)").bindparams(codes=[c for c, *_ in UNITS]))
    op.execute(sa.text("DELETE FROM roles WHERE code = ANY(:codes)").bindparams(codes=[c for c, _ in ROLES]))
