"""Определение столбцов, типов и пригодности к временному анализу."""

from collections import Counter

from app.models.enums import PeriodGranularity
from app.services.ingest.indicators import (
    IndicatorCatalog, is_category_name, is_long_indicator_name, is_long_value_name, is_period_name,
)
from app.services.ingest.numbers import is_missing, parse_number
from app.services.ingest.periods import infer_granularity, parse_period
from app.services.ingest.types import ColumnKind, ColumnProfile, Table, TableFormat

PREVIEW_ROWS = 10
MIN_PERIOD_SHARE = 0.7
MIN_NUMBER_SHARE = 0.7
MIN_PERIODS_FOR_TREND = 3


def detect_format(headers: list[str]) -> TableFormat:
    if any(is_long_indicator_name(h) for h in headers) and any(is_long_value_name(h) for h in headers):
        return "long"
    return "wide"


def suggest_period_column(headers: list[str], profiles: list[ColumnProfile]) -> str | None:
    named = next((h for h in headers if is_period_name(h)), None)
    if named:
        return named
    period_like = [p for p in profiles if p.kind == "period"]
    if period_like:
        return max(period_like, key=lambda p: p.non_empty).name
    return None


def suggest_category_column(headers: list[str]) -> str | None:
    return next((h for h in headers if is_category_name(h)), None)


def profile_columns(table: Table, catalog: IndicatorCatalog) -> list[ColumnProfile]:
    return [_profile(table, index, catalog) for index, _ in enumerate(table.headers)]


def _profile(table: Table, index: int, catalog: IndicatorCatalog) -> ColumnProfile:
    name = table.headers[index]
    values = [row[index] if index < len(row) else None for row in table.rows]
    filled = [v for v in values if not is_missing(v)]
    kinds = Counter()
    for value in filled:
        if parse_period(value):
            kinds["period"] += 1
        elif parse_number(value)[2] is None:
            kinds["number"] += 1
        else:
            kinds["text"] += 1
    kind = _majority(kinds, len(filled))
    matched = catalog.match(name)
    samples = [v for v in filled[:PREVIEW_ROWS]]
    return ColumnProfile(
        name=name,
        kind=kind,
        non_empty=len(filled),
        inferred_granularity=infer_granularity(values) if kind == "period" else None,
        matched_indicator_code=matched.code if matched else None,
        matched_indicator_name=matched.name if matched else None,
        sample_values=samples[:5],
    )


def _majority(kinds: Counter, filled: int) -> ColumnKind:
    if filled == 0:
        return "empty"
    if not kinds:
        return "empty"
    winner, count = kinds.most_common(1)[0]
    share = count / filled
    if winner == "period" and share >= MIN_PERIOD_SHARE:
        return "period"
    if winner == "number" and share >= MIN_NUMBER_SHARE:
        return "number"
    if winner == "text" and share >= MIN_PERIOD_SHARE:
        return "text"
    if len(kinds) > 1:
        return "mixed"
    return winner  # type: ignore[return-value]


def time_analysis(period_profile: ColumnProfile | None, distinct_periods: int,
                  granularity: PeriodGranularity | None, has_errors: bool) -> dict:
    if period_profile is None:
        return {
            "possible": False,
            "reason": "Не выбран столбец с периодом, пригодный для временного анализа",
            "distinct_periods": 0,
            "granularity": None,
        }
    if has_errors:
        return {
            "possible": False,
            "reason": "В столбце периода есть некорректные значения",
            "distinct_periods": distinct_periods,
            "granularity": granularity.value if granularity else None,
        }
    if distinct_periods < MIN_PERIODS_FOR_TREND:
        return {
            "possible": False,
            "reason": f"Для анализа динамики нужно не менее {MIN_PERIODS_FOR_TREND} различных периодов",
            "distinct_periods": distinct_periods,
            "granularity": granularity.value if granularity else None,
        }
    return {
        "possible": True,
        "reason": None,
        "distinct_periods": distinct_periods,
        "granularity": granularity.value if granularity else None,
        "period_column": period_profile.name,
    }
