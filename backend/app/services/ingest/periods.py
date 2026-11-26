"""Разбор периодов наблюдения: месяц, квартал, год."""

import re
from datetime import date, datetime

from app.models.enums import PeriodGranularity
from app.repositories.reference_repository import period_end

_MONTH = re.compile(r"^(\d{4})[-./](\d{1,2})(?:[-./](\d{1,2}))?$")
_QUARTER = re.compile(r"^(\d{4})[-.\s]*[QqКк][-.\s]*([1-4])$")
_YEAR = re.compile(r"^(\d{4})$")
_RU_MONTH = re.compile(r"^(\d{1,2})[-./](\d{4})$")


def parse_period(raw: str | None, expected: PeriodGranularity | None = None) -> tuple[date, PeriodGranularity] | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    parsed = _parse(text)
    if parsed is None:
        return None
    start, granularity = parsed
    if expected is not None and granularity != expected:
        if expected == PeriodGranularity.MONTH and granularity in {PeriodGranularity.QUARTER, PeriodGranularity.YEAR}:
            return None
        if expected == PeriodGranularity.QUARTER and start.month not in (1, 4, 7, 10):
            return None
        if expected == PeriodGranularity.YEAR and start.month != 1:
            return None
        if expected == PeriodGranularity.QUARTER and granularity == PeriodGranularity.MONTH:
            if start.month not in (1, 4, 7, 10):
                return None
            return start, PeriodGranularity.QUARTER
        if expected == PeriodGranularity.YEAR and granularity == PeriodGranularity.MONTH:
            if start.month != 1:
                return None
            return date(start.year, 1, 1), PeriodGranularity.YEAR
    return start, granularity


def _year_ok(year: int) -> bool:
    return 1900 <= year <= 2100


def _parse(text: str) -> tuple[date, PeriodGranularity] | None:
    match = _QUARTER.fullmatch(text.replace(" ", ""))
    if match:
        year, quarter = int(match.group(1)), int(match.group(2))
        if not _year_ok(year):
            return None
        return date(year, 1 + (quarter - 1) * 3, 1), PeriodGranularity.QUARTER
    match = _MONTH.fullmatch(text)
    if match:
        year, month = int(match.group(1)), int(match.group(2))
        day = int(match.group(3) or 1)
        if not _year_ok(year) or not 1 <= month <= 12 or day != 1:
            return None
        return date(year, month, 1), PeriodGranularity.MONTH
    match = _RU_MONTH.fullmatch(text)
    if match:
        month, year = int(match.group(1)), int(match.group(2))
        if not _year_ok(year) or not 1 <= month <= 12:
            return None
        return date(year, month, 1), PeriodGranularity.MONTH
    match = _YEAR.fullmatch(text)
    if match:
        year = int(match.group(1))
        if not _year_ok(year):
            return None
        return date(year, 1, 1), PeriodGranularity.YEAR
    try:
        parsed = datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None
    if parsed.day != 1:
        return None
    return parsed, PeriodGranularity.MONTH


def infer_granularity(values: list[str | None]) -> PeriodGranularity | None:
    found: dict[PeriodGranularity, int] = {}
    for value in values:
        parsed = parse_period(value)
        if parsed:
            found[parsed[1]] = found.get(parsed[1], 0) + 1
    if not found:
        return None
    return max(found, key=found.get)


def period_label(start: date, granularity: PeriodGranularity) -> str:
    end = period_end(granularity, start)
    return f"{start.isoformat()}…{end.isoformat()}"
