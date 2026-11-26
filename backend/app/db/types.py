"""Типы столбцов, общие для моделей.

Значения показателей (в том числе денежные суммы) хранятся в NUMERIC с фиксированной
точностью: 16 знаков целой части и 4 дробной покрывают суммы до 10^16 руб. с копейками
и натуральные показатели с дробной частью. Статистические характеристики (z-оценки,
коэффициенты корреляции, p-значения, ошибки прогноза) — результат вычислений
с плавающей точкой и хранятся в DOUBLE PRECISION без потери информации.
"""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Double, Enum, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

AMOUNT = Numeric(20, 4)
WEIGHT = Numeric(6, 5)
UNIT_INTERVAL = Numeric(6, 5)
SCORE_100 = Numeric(5, 2)
PARAMETER_NUMBER = Numeric(20, 6)
STATISTIC = Double()


def enum_type(enum_cls: type[PyEnum], name: str) -> Enum:
    """Перечисление как VARCHAR с CHECK: добавление значения не требует ALTER TYPE."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda members: [member.value for member in members],
        validate_strings=True,
    )


def created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
