from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from app.models.enums import IssueSeverity, PeriodGranularity

TableFormat = Literal["wide", "long"]
SourceFormat = Literal["csv", "xlsx"]
ColumnKind = Literal["period", "number", "text", "empty", "mixed"]


class IssueCode(StrEnum):
    EMPTY_FILE = "empty_file"
    UNSUPPORTED_FORMAT = "unsupported_format"
    UNREADABLE = "unreadable_file"
    TOO_LARGE = "file_too_large"
    TOO_MANY_ROWS = "too_many_rows"
    NO_NUMERIC_COLUMNS = "no_numeric_columns"
    INVALID_PERIOD = "invalid_period"
    INVALID_NUMBER = "invalid_number"
    DUPLICATE_ROW = "duplicate_row"
    MISSING_VALUE = "missing_values"
    UNKNOWN_PERIOD_COLUMN = "unknown_period_column"
    UNKNOWN_INDICATOR_COLUMN = "unknown_indicator_column"
    NO_INDICATORS = "no_indicators"
    FORMULA_CELL = "formula_without_value"
    DECIMAL_SEPARATOR = "decimal_separator_normalized"
    WHITESPACE_TRIMMED = "whitespace_trimmed"
    EXCEL_DATE = "excel_date_converted"
    MERGED_OVERLAP = "merged_overlap"


@dataclass(frozen=True)
class CheckIssue:
    severity: IssueSeverity
    code: str
    message: str
    row_number: int | None = None
    column_name: str | None = None


@dataclass(frozen=True)
class Transformation:
    code: str
    message: str
    column_name: str | None = None


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str | None]]
    source_format: SourceFormat
    encoding: str | None = None
    transformations: list[Transformation] = field(default_factory=list)
    issues: list[CheckIssue] = field(default_factory=list)


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    kind: ColumnKind
    non_empty: int
    inferred_granularity: PeriodGranularity | None
    matched_indicator_code: str | None
    matched_indicator_name: str | None
    sample_values: list[str]


@dataclass
class ParsedCell:
    period_start: date
    indicator_code: str
    category: str | None
    value: Decimal | None
    source_row: int
    source_column: str


@dataclass
class ParseResult:
    cells: list[ParsedCell]
    issues: list[CheckIssue]
    transformations: list[Transformation]
    granularity: PeriodGranularity
    table_format: TableFormat
    period_column: str
    indicator_columns: list[str]
    category_column: str | None
    ready_for_save: bool
