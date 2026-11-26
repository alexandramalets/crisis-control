"""Подписи сводной оценки 0–100. Шкала едина для панели и заключения."""

from decimal import Decimal

ASSESSMENT_DISCLAIMER = (
    "Оценка 0–100 — ориентир по выбранному периоду, не диагноз кризиса."
)

ASSESSMENT_METHOD = (
    "Последнее значение показателя нормализуется в диапазоне ряда с учётом направления влияния. Веса по умолчанию равные."
)


def interpret_score(score: Decimal | float | None) -> str | None:
    if score is None:
        return None
    value = float(score)
    if value >= 75:
        return "Устойчивое состояние"
    if value >= 50:
        return "Умеренный риск"
    if value >= 25:
        return "Повышенный риск"
    return "Выраженные признаки риска"
