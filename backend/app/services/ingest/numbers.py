"""Разбор числовых значений показателей без молчаливой потери данных."""

from decimal import Decimal, InvalidOperation

from app.services.ingest.types import IssueCode, Transformation

MISSING_TOKENS = {
    "", "-", "—", "–", "n/a", "na", "null", "none", "nan",
    "нет данных", "нет", "н/д", ".",
}

_MAX_DIGITS, _DECIMAL_PLACES = 20, 4


def is_missing(raw: str | None) -> bool:
    return raw is None or raw.strip().lower() in MISSING_TOKENS


def parse_number(raw: str | None) -> tuple[Decimal | None, list[Transformation], str | None]:
    """Возвращает (значение, преобразования, ошибка). None без ошибки — пропуск."""
    if is_missing(raw):
        return None, [], None
    text = raw.strip()
    transformations: list[Transformation] = []
    if text != raw:
        transformations.append(Transformation(
            IssueCode.WHITESPACE_TRIMMED, "Удалены пробелы по краям значения",
        ))
    normalized = text.replace("\u00a0", "").replace(" ", "")
    if "," in normalized and "." in normalized:
        if normalized.rfind(",") > normalized.rfind("."):
            normalized = normalized.replace(".", "").replace(",", ".")
            transformations.append(Transformation(
                IssueCode.DECIMAL_SEPARATOR, "Разделитель дробной части «,» заменён на «.»",
            ))
        else:
            normalized = normalized.replace(",", "")
    elif "," in normalized:
        normalized = normalized.replace(",", ".")
        transformations.append(Transformation(
            IssueCode.DECIMAL_SEPARATOR, "Разделитель дробной части «,» заменён на «.»",
        ))
    if normalized.endswith("%"):
        return None, transformations, "Проценты в исходном файле не принимаются как значение показателя"
    try:
        value = Decimal(normalized)
    except InvalidOperation:
        return None, transformations, f"Некорректное число: «{text}»"
    if not value.is_finite():
        return None, transformations, f"Некорректное число: «{text}»"
    sign, digits, exponent = value.as_tuple()
    decimal_places = -exponent if exponent < 0 else 0
    whole_digits = len(digits) - decimal_places
    if decimal_places > _DECIMAL_PLACES:
        return None, transformations, f"Не более {_DECIMAL_PLACES} знаков после запятой: «{text}»"
    if whole_digits + max(decimal_places, 0) > _MAX_DIGITS or whole_digits > _MAX_DIGITS - _DECIMAL_PLACES:
        return None, transformations, f"Слишком большое число: «{text}»"
    return value, transformations, None
