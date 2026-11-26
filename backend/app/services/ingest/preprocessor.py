"""Проверка качества и разбор в «длинный» формат. Исходный файл не изменяется."""

from collections import defaultdict

from app.models.enums import IssueSeverity, PeriodGranularity
from app.services.errors import ValidationFailedError
from app.services.ingest.indicators import IndicatorCatalog, is_long_indicator_name, is_long_value_name
from app.services.ingest.numbers import parse_number
from app.services.ingest.periods import infer_granularity, parse_period
from app.services.ingest.schema_inspector import (
    detect_format, profile_columns, suggest_category_column, suggest_period_column, time_analysis,
)
from app.services.ingest.types import (
    CheckIssue, ColumnProfile, IssueCode, ParsedCell, ParseResult, Table, Transformation,
)

MAX_ISSUE_DETAILS = 50


def inspect_table(table: Table, catalog: IndicatorCatalog, preview_rows: int = 10) -> dict:
    profiles = profile_columns(table, catalog)
    table_format = detect_format(table.headers)
    period_name = suggest_period_column(table.headers, profiles)
    category_name = suggest_category_column(table.headers)
    numeric = [p for p in profiles if p.kind in {"number", "mixed"} and p.name != period_name]
    mapped = [p for p in numeric if p.matched_indicator_code]
    unmapped = [p.name for p in numeric if not p.matched_indicator_code]
    period_profile = next((p for p in profiles if p.name == period_name), None)
    preview = []
    for row in table.rows[:preview_rows]:
        preview.append({header: (row[i] if i < len(row) else None) for i, header in enumerate(table.headers)})
    return {
        "format": table_format,
        "source_format": table.source_format,
        "encoding": table.encoding,
        "rows": len(table.rows),
        "columns": [_column_payload(p) for p in profiles],
        "preview": preview,
        "suggested_period_column": period_name,
        "suggested_category_column": category_name,
        "suggested_indicators": [
            {"column": p.name, "code": p.matched_indicator_code, "name": p.matched_indicator_name}
            for p in mapped
        ],
        "unmapped_numeric_columns": unmapped,
        "time_analysis": time_analysis(
            period_profile,
            _distinct_periods(table, period_name),
            period_profile.inferred_granularity if period_profile else None,
            False,
        ),
    }


def parse_table(
    table: Table,
    catalog: IndicatorCatalog,
    *,
    period_column: str | None,
    indicator_columns: list[str] | None,
    category_column: str | None,
    granularity: PeriodGranularity | None,
) -> ParseResult:
    profiles = profile_columns(table, catalog)
    table_format = detect_format(table.headers)
    period_name = period_column or suggest_period_column(table.headers, profiles)
    if not period_name or period_name not in table.headers:
        raise ValidationFailedError(
            "Некорректное временное поле: укажите столбец с периодом (например, period или ГГГГ-ММ)",
            code=IssueCode.UNKNOWN_PERIOD_COLUMN,
        )
    category_name = category_column if category_column is not None else suggest_category_column(table.headers)
    if category_name and category_name not in table.headers:
        raise ValidationFailedError(f"Столбец категории «{category_name}» отсутствует в файле")

    if table_format == "long":
        selected = _long_columns(table.headers)
    else:
        selected = _wide_indicators(table, profiles, catalog, period_name, category_name, indicator_columns)

    expected_granularity = granularity or infer_granularity(_column_values(table, period_name))
    if expected_granularity is None:
        expected_granularity = PeriodGranularity.MONTH

    cells, issues, transformations = [], list(table.issues), list(table.transformations)
    seen: dict[tuple, list[int]] = defaultdict(list)
    index = {name: i for i, name in enumerate(table.headers)}

    if table_format == "long":
        _parse_long(table, catalog, period_name, category_name, expected_granularity,
                    selected, index, cells, issues, transformations, seen)
    else:
        _parse_wide(table, catalog, period_name, category_name, expected_granularity,
                    selected, index, cells, issues, transformations, seen)

    for key, rows in seen.items():
        if len(rows) > 1:
            issues.append(CheckIssue(
                IssueSeverity.ERROR, IssueCode.DUPLICATE_ROW,
                f"Повторяющиеся строки для показателя «{key[1]}», периода {key[0]}"
                + (f", категории «{key[2]}»" if key[2] else "")
                + f" (строки {', '.join(map(str, rows))})",
                rows[0], key[1],
            ))

    blocking = any(item.severity == IssueSeverity.ERROR for item in issues)
    return ParseResult(
        cells=cells, issues=issues, transformations=_unique_transformations(transformations),
        granularity=expected_granularity, table_format=table_format, period_column=period_name,
        indicator_columns=selected, category_column=category_name, ready_for_save=not blocking and bool(cells),
    )


def quality_summary(result: ParseResult, table: Table | None = None) -> dict:
    missing = sum(1 for cell in result.cells if cell.value is None)
    errors = [i for i in result.issues if i.severity == IssueSeverity.ERROR]
    warnings = [i for i in result.issues if i.severity == IssueSeverity.WARNING]
    periods = {cell.period_start for cell in result.cells}
    period_errors = [i for i in errors if i.code == IssueCode.INVALID_PERIOD]
    return {
        "ready_for_analysis": result.ready_for_save,
        "rows": len(table.rows) if table else None,
        "values_count": len(result.cells),
        "missing_count": missing,
        "duplicate_count": sum(1 for i in errors if i.code == IssueCode.DUPLICATE_ROW),
        "invalid_number_count": sum(1 for i in errors if i.code == IssueCode.INVALID_NUMBER),
        "invalid_period_count": len(period_errors),
        "indicators": sorted({cell.indicator_code for cell in result.cells}),
        "granularity": result.granularity.value,
        "period_from": min(periods).isoformat() if periods else None,
        "period_to": max(periods).isoformat() if periods else None,
        "distinct_periods": len(periods),
        "time_analysis": time_analysis(
            ColumnProfile(result.period_column, "period", len(periods), result.granularity, None, None, []),
            len(periods), result.granularity, bool(period_errors),
        ),
        "transformations": [{"code": t.code, "message": t.message, "column_name": t.column_name}
                            for t in result.transformations],
        "issues": [_issue_payload(i) for i in result.issues[:MAX_ISSUE_DETAILS]],
        "issues_truncated": max(0, len(result.issues) - MAX_ISSUE_DETAILS),
        "error_count": len(errors),
        "warning_count": len(warnings),
    }


def _wide_indicators(table, profiles, catalog, period_name, category_name, indicator_columns) -> list[str]:
    reserved = {period_name, category_name} - {None}
    if indicator_columns:
        missing = [name for name in indicator_columns if name not in table.headers]
        if missing:
            raise ValidationFailedError(
                "Выбранные столбцы показателей отсутствуют в файле",
                details={"unknown_columns": missing},
            )
        unmapped = [name for name in indicator_columns if catalog.match(name) is None]
        if unmapped:
            raise ValidationFailedError(
                "Столбцы не соответствуют известным показателям. "
                "Доступны финансовые и операционные показатели справочника "
                "(выручка, прибыль, задолженность, денежные средства, продажи, запасы и др.)",
                details={"unmapped_columns": unmapped},
                code=IssueCode.UNKNOWN_INDICATOR_COLUMN,
            )
        return indicator_columns
    mapped = [p.name for p in profiles
              if p.name not in reserved and p.matched_indicator_code and p.kind in {"number", "mixed", "empty"}]
    if not mapped:
        raise ValidationFailedError(
            "В файле нет пригодных числовых столбцов с известными показателями. "
            "Добавьте, например, revenue (выручка) или profit (прибыль)",
            code=IssueCode.NO_NUMERIC_COLUMNS,
        )
    return mapped


def _long_columns(headers: list[str]) -> list[str]:
    indicator = next(h for h in headers if is_long_indicator_name(h))
    value = next(h for h in headers if is_long_value_name(h))
    return [indicator, value]


def _parse_wide(table, catalog, period_name, category_name, granularity, selected, index,
                cells, issues, transformations, seen) -> None:
    for row_number, row in enumerate(table.rows, start=2):
        period = _period_cell(row, index[period_name], period_name, row_number, granularity, issues)
        category = _category_cell(row, index, category_name)
        if period is None:
            continue
        for column in selected:
            raw = _at(row, index[column])
            value, trans, error = parse_number(raw)
            transformations.extend(_with_column(trans, column))
            if error:
                issues.append(CheckIssue(
                    IssueSeverity.ERROR, IssueCode.INVALID_NUMBER,
                    f"Строка {row_number}, столбец «{column}»: {error}",
                    row_number, column,
                ))
                continue
            if value is None and not _blank(raw):
                pass
            if value is None:
                issues.append(CheckIssue(
                    IssueSeverity.WARNING, IssueCode.MISSING_VALUE,
                    f"Строка {row_number}, столбец «{column}»: пропущенное значение сохраняется как пропуск",
                    row_number, column,
                ))
            indicator = catalog.match(column)
            key = (period.isoformat(), indicator.code, category)
            seen[key].append(row_number)
            cells.append(ParsedCell(period, indicator.code, category, value, row_number, column))


def _parse_long(table, catalog, period_name, category_name, granularity, selected, index,
                cells, issues, transformations, seen) -> None:
    indicator_col, value_col = selected
    for row_number, row in enumerate(table.rows, start=2):
        period = _period_cell(row, index[period_name], period_name, row_number, granularity, issues)
        category = _category_cell(row, index, category_name)
        label = _at(row, index[indicator_col])
        if period is None:
            continue
        if not label:
            issues.append(CheckIssue(
                IssueSeverity.ERROR, IssueCode.UNKNOWN_INDICATOR_COLUMN,
                f"Строка {row_number}: не указан показатель",
                row_number, indicator_col,
            ))
            continue
        indicator = catalog.match(label)
        if indicator is None:
            issues.append(CheckIssue(
                IssueSeverity.ERROR, IssueCode.UNKNOWN_INDICATOR_COLUMN,
                f"Строка {row_number}: неизвестный показатель «{label}»",
                row_number, indicator_col,
            ))
            continue
        value, trans, error = parse_number(_at(row, index[value_col]))
        transformations.extend(_with_column(trans, value_col))
        if error:
            issues.append(CheckIssue(
                IssueSeverity.ERROR, IssueCode.INVALID_NUMBER,
                f"Строка {row_number}, столбец «{value_col}»: {error}",
                row_number, value_col,
            ))
            continue
        if value is None:
            issues.append(CheckIssue(
                IssueSeverity.WARNING, IssueCode.MISSING_VALUE,
                f"Строка {row_number}: пропущенное значение показателя «{indicator.code}»",
                row_number, value_col,
            ))
        key = (period.isoformat(), indicator.code, category)
        seen[key].append(row_number)
        cells.append(ParsedCell(period, indicator.code, category, value, row_number, value_col))


def _period_cell(row, column_index, column_name, row_number, granularity, issues):
    raw = _at(row, column_index)
    parsed = parse_period(raw, granularity)
    if parsed is None:
        issues.append(CheckIssue(
            IssueSeverity.ERROR, IssueCode.INVALID_PERIOD,
            f"Строка {row_number}: некорректное временное поле «{raw or ''}». "
            "Ожидается начало периода: ГГГГ-ММ, ГГГГ-ММ-ДД (день 01), ГГГГ-Qn или ГГГГ",
            row_number, column_name,
        ))
        return None
    return parsed[0]


def _category_cell(row, index, category_name: str | None) -> str | None:
    if not category_name:
        return None
    value = _at(row, index[category_name])
    return value.strip() if value else None


def _at(row, index: int) -> str | None:
    return row[index] if index < len(row) else None


def _blank(raw: str | None) -> bool:
    return raw is None or not raw.strip()


def _column_values(table: Table, name: str) -> list[str | None]:
    index = table.headers.index(name)
    return [row[index] if index < len(row) else None for row in table.rows]


def _distinct_periods(table: Table, period_name: str | None) -> int:
    if not period_name:
        return 0
    starts = {parsed[0] for value in _column_values(table, period_name) if (parsed := parse_period(value))}
    return len(starts)


def _with_column(items: list[Transformation], column: str) -> list[Transformation]:
    return [Transformation(item.code, item.message, column) for item in items]


def _unique_transformations(items: list[Transformation]) -> list[Transformation]:
    seen, unique = set(), []
    for item in items:
        key = (item.code, item.column_name)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _column_payload(profile: ColumnProfile) -> dict:
    return {
        "name": profile.name,
        "kind": profile.kind,
        "non_empty": profile.non_empty,
        "inferred_granularity": profile.inferred_granularity.value if profile.inferred_granularity else None,
        "indicator_code": profile.matched_indicator_code,
        "indicator_name": profile.matched_indicator_name,
        "usable_for_time_analysis": profile.kind == "period",
        "sample_values": profile.sample_values,
    }


def _issue_payload(issue: CheckIssue) -> dict:
    return {
        "severity": issue.severity.value,
        "code": issue.code,
        "message": issue.message,
        "row_number": issue.row_number,
        "column_name": issue.column_name,
    }
