"""Чтение CSV и XLSX без выполнения формул и макросов."""

import csv
import io
import zipfile
from datetime import date, datetime
from decimal import Decimal

from openpyxl import load_workbook

from app.models.enums import IssueSeverity  # noqa: F401 — used in merge warnings
from app.services.errors import PayloadTooLargeError, ValidationFailedError
from app.services.ingest.filenames import extension, original_filename
from app.services.ingest.indicators import is_period_name, normalize_label
from app.services.ingest.types import CheckIssue, IssueCode, Table, Transformation

SKIP_SHEETS = {
    "описание", "показатели", "планы", "границы", "мероприятия", "мероприятиядляинтерфейса",
    "каковнести", "каквнести", "легенда", "readme", "notes",
}

ALLOWED_EXTENSIONS = {"csv", "xlsx"}
XLSX_MAGIC = b"PK\x03\x04"
MAX_COLUMNS = 40


def read_table(content: bytes, filename: str, *, max_bytes: int, max_rows: int) -> Table:
    if len(content) > max_bytes:
        raise PayloadTooLargeError(
            f"Размер файла превышает допустимые {max_bytes // (1024 * 1024)} МБ",
            code=IssueCode.TOO_LARGE,
        )
    if not content or not content.strip():
        raise ValidationFailedError("Файл пуст", code=IssueCode.EMPTY_FILE)

    name = original_filename(filename)
    ext = extension(name)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationFailedError(
            "Неподдерживаемый формат файла. Допустимы CSV и XLSX",
            details={"filename": name, "extension": ext or None},
            code=IssueCode.UNSUPPORTED_FORMAT,
        )
    is_zip = content.startswith(XLSX_MAGIC)
    if ext == "xlsx" and not is_zip:
        raise ValidationFailedError(
            "Расширение XLSX не соответствует содержимому файла",
            code=IssueCode.UNSUPPORTED_FORMAT,
        )
    if ext == "csv" and is_zip:
        raise ValidationFailedError(
            "Расширение CSV не соответствует содержимому файла",
            code=IssueCode.UNSUPPORTED_FORMAT,
        )
    return _read_xlsx(content, max_rows) if ext == "xlsx" else _read_csv(content, max_rows)


def _read_csv(content: bytes, max_rows: int) -> Table:
    encoding, text = _decode_csv(content)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    try:
        header_row = next(reader)
    except StopIteration:
        raise ValidationFailedError("Файл пуст", code=IssueCode.EMPTY_FILE) from None
    headers = _normalize_headers(header_row)
    rows, issues = [], []
    for index, raw in enumerate(reader, start=2):
        if index - 1 > max_rows:
            raise ValidationFailedError(
                f"Число строк превышает допустимые {max_rows}",
                code=IssueCode.TOO_MANY_ROWS,
            )
        if _row_empty(raw):
            continue
        padded = list(raw) + [None] * (len(headers) - len(raw))
        rows.append([_cell_text(value) for value in padded[: len(headers)]])
    if not rows:
        raise ValidationFailedError("Файл не содержит строк данных", code=IssueCode.EMPTY_FILE)
    return Table(headers=headers, rows=rows, source_format="csv", encoding=encoding, issues=issues)


def _decode_csv(content: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return encoding, content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValidationFailedError(
        "Не удалось прочитать файл: неизвестная кодировка. Сохраните CSV в UTF-8",
        code=IssueCode.UNREADABLE,
    )


def _read_xlsx(content: bytes, max_rows: int) -> Table:
    try:
        if not zipfile.is_zipfile(io.BytesIO(content)):
            raise ValidationFailedError("Файл не является книгой Excel (XLSX)", code=IssueCode.UNSUPPORTED_FORMAT)
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False)
    except ValidationFailedError:
        raise
    except Exception as exc:
        raise ValidationFailedError(
            "Не удалось прочитать книгу Excel. Файл повреждён или защищён паролем",
            code=IssueCode.UNREADABLE,
        ) from exc
    try:
        parts: list[Table] = []
        for sheet in workbook.worksheets:
            title = normalize_label(sheet.title or "")
            if title in SKIP_SHEETS:
                continue
            table = _sheet_table(sheet, max_rows)
            if table is not None:
                parts.append(table)
        if not parts:
            raise ValidationFailedError("Файл не содержит строк данных", code=IssueCode.EMPTY_FILE)
        return _merge_tables(parts)
    finally:
        workbook.close()


def _sheet_table(sheet, max_rows: int) -> Table | None:
    rows_iter = sheet.iter_rows()
    try:
        header_cells = next(rows_iter)
    except StopIteration:
        return None
    headers = _normalize_headers([cell.value for cell in header_cells])
    if not any(is_period_name(name) or name.casefold() == "period" for name in headers):
        if not any(headers):
            return None
    data, issues, transformations = [], [], []
    excel_dates = 0
    for index, row in enumerate(rows_iter, start=2):
        if index - 1 > max_rows:
            raise ValidationFailedError(
                f"Число строк превышает допустимые {max_rows}",
                code=IssueCode.TOO_MANY_ROWS,
            )
        values, row_issues, dates = _xlsx_row(row, headers, index)
        if _row_empty(values):
            continue
        issues.extend(row_issues)
        excel_dates += dates
        data.append(values)
    if not data:
        return None
    if excel_dates:
        transformations.append(Transformation(
            IssueCode.EXCEL_DATE,
            f"Даты Excel преобразованы в текст ISO в {excel_dates} ячейках; исходный файл не изменён",
        ))
    return Table(headers=headers, rows=data, source_format="xlsx",
                 transformations=transformations, issues=issues)


def _merge_tables(parts: list[Table]) -> Table:
    if len(parts) == 1:
        return parts[0]
    period_names = []
    for table in parts:
        period_names.append(next((h for h in table.headers if is_period_name(h) or h.casefold() == "period"), table.headers[0]))
    headers: list[str] = []
    seen_headers: set[str] = set()
    for table, period_name in zip(parts, period_names):
        for name in table.headers:
            key = "period" if name == period_name else name
            if key not in seen_headers:
                seen_headers.add(key)
                headers.append("period" if key == "period" else name)
    if "period" not in headers:
        headers.insert(0, "period")
    by_period: dict[str, dict[str, str | None]] = {}
    issues = []
    transformations = []
    for table, period_name in zip(parts, period_names):
        issues.extend(table.issues)
        transformations.extend(table.transformations)
        index = {name: i for i, name in enumerate(table.headers)}
        for row in table.rows:
            period = row[index[period_name]] if period_name in index else None
            if not period:
                continue
            current = by_period.setdefault(str(period), {})
            current["period"] = str(period)
            for name in table.headers:
                if name == period_name:
                    continue
                value = row[index[name]] if name in index else None
                if value is None or str(value).strip() == "":
                    continue
                previous = current.get(name)
                if previous not in (None, "", value) and previous != value:
                    issues.append(CheckIssue(
                        IssueSeverity.WARNING, IssueCode.MERGED_OVERLAP,
                        f"Период {period}, столбец «{name}»: разные значения объединены, оставлено последнее ({value})",
                    ))
                current[name] = value
            if len(headers) < MAX_COLUMNS:
                for name in current:
                    if name not in seen_headers:
                        seen_headers.add(name)
                        headers.append(name)
    rows = [[by_period[period].get(name) for name in headers] for period in sorted(by_period)]
    transformations.append(Transformation(
        IssueCode.MERGED_OVERLAP,
        f"Объединены листы книги: {len(parts)} фрагмента, {len(by_period)} периодов",
    ))
    return Table(headers=headers[:MAX_COLUMNS], rows=rows, source_format="xlsx",
                 transformations=transformations, issues=issues)


def _xlsx_row(row, headers: list[str], row_number: int) -> tuple[list[str | None], list[CheckIssue], int]:
    issues, dates = [], 0
    values: list[str | None] = [None] * len(headers)
    for column, cell in enumerate(row):
        if column >= len(headers):
            break
        header = headers[column]
        data_type = getattr(cell, "data_type", None)
        value = cell.value
        if data_type == "f" and value is None:
            issues.append(CheckIssue(
                IssueSeverity.WARNING, IssueCode.FORMULA_CELL,
                f"Строка {row_number}, столбец «{header}»: формула без сохранённого значения не вычисляется",
                row_number, header,
            ))
            continue
        text, is_date = _excel_value(value)
        values[column] = text
        dates += int(is_date)
    return values, issues, dates


def _excel_value(value) -> tuple[str | None, bool]:
    if value is None:
        return None, False
    if isinstance(value, datetime):
        return value.date().isoformat(), True
    if isinstance(value, date):
        return value.isoformat(), True
    if isinstance(value, bool):
        return "1" if value else "0", False
    if isinstance(value, Decimal):
        return format(value, "f"), False
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value), False
    if isinstance(value, float):
        return format(Decimal(str(value)).normalize(), "f"), False
    return _cell_text(value), False


def _normalize_headers(raw: list) -> list[str]:
    headers, seen = [], {}
    for index, item in enumerate(raw[:MAX_COLUMNS]):
        name = _cell_text(item) or f"column_{index + 1}"
        count = seen.get(name, 0)
        seen[name] = count + 1
        headers.append(name if count == 0 else f"{name}_{count + 1}")
    if not any(h != f"column_{i + 1}" for i, h in enumerate(headers)):
        # all empty - still ok if we have generated names, but empty file of empty headers
        pass
    if not headers:
        raise ValidationFailedError("Файл не содержит столбцов", code=IssueCode.EMPTY_FILE)
    return headers


def _cell_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _row_empty(values) -> bool:
    return all(value is None or str(value).strip() == "" for value in values)
