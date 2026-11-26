"""Разбор файла планов и границ. Не смешивается с загрузкой рядов показателей."""

from __future__ import annotations

import csv
import io
from datetime import date, datetime
from decimal import Decimal

from openpyxl import load_workbook

from app.services.errors import ValidationFailedError
from app.services.ingest.filenames import extension
from app.services.ingest.indicators import normalize_label  # sheet titles and column aliases
from app.services.ingest.numbers import parse_number

KIND_MAP = {
    "plan": "plan", "план": "plan",
    "norm": "norm", "норматив": "norm",
    "target": "target", "цель": "target", "целевое": "target",
}

CODE_ALIASES = {"indicator_code", "код", "кодпоказателя", "показатель", "indicator"}
KIND_ALIASES = {"kind", "тип", "type"}
VALUE_ALIASES = {"value", "значение"}
LOWER_ALIASES = {"lower_bound", "нижняя", "нижняяграница", "min"}
UPPER_ALIASES = {"upper_bound", "верхняя", "верхняяграница", "max"}
SOURCE_ALIASES = {"source", "источник"}
NOTES_ALIASES = {"notes", "описание", "description"}
FROM_ALIASES = {"valid_from", "с", "period_from"}
TO_ALIASES = {"valid_to", "по", "period_to"}
NAME_ALIASES = {"name", "наименование", "название"}
METHOD_ALIASES = {"methodology", "методика", "источникиметодика"}
SKIP_SHEETS = {
    "мероприятия", "мероприятиядляинтерфейса", "каковнести", "каквнести",
    "описание", "легенда", "readme", "notes",
}


def parse_profile_file(content: bytes, filename: str) -> dict:
    ext = extension(filename)
    if ext == "xlsx":
        rows = _xlsx_rows(content)
    elif ext == "csv":
        rows = _csv_rows(content)
    else:
        raise ValidationFailedError("Для нормативов допустимы CSV и XLSX")
    targets, thresholds = [], []
    for headers, data in rows:
        index = {_key(h): i for i, h in enumerate(headers)}
        for raw in data:
            code = _cell(raw, index, CODE_ALIASES)
            name = _cell(raw, index, NAME_ALIASES)
            kind_raw = _cell(raw, index, KIND_ALIASES)
            kind = KIND_MAP.get(normalize_label(kind_raw or ""))
            value, _, err = parse_number(_cell(raw, index, VALUE_ALIASES))
            lower, _, _ = parse_number(_cell(raw, index, LOWER_ALIASES))
            upper, _, _ = parse_number(_cell(raw, index, UPPER_ALIASES))
            source = _cell(raw, index, SOURCE_ALIASES)
            notes = _cell(raw, index, NOTES_ALIASES)
            methodology = _cell(raw, index, METHOD_ALIASES)
            if kind and value is not None and (code or name):
                targets.append({
                    "indicator_code": (code or "").strip().casefold() or "unknown",
                    "name": name,
                    "kind": kind,
                    "value": value,
                    "source": source,
                    "notes": notes,
                    "valid_from": _date(_cell(raw, index, FROM_ALIASES)),
                    "valid_to": _date(_cell(raw, index, TO_ALIASES)),
                })
            elif (lower is not None or upper is not None) and (code or name):
                thresholds.append({
                    "indicator_code": (code or "").strip().casefold() or "unknown",
                    "name": name,
                    "lower_bound": lower,
                    "upper_bound": upper,
                    "source": source,
                    "notes": notes,
                    "methodology": methodology or source,
                })
    return {"targets": targets, "thresholds": thresholds}


def _xlsx_rows(content: bytes) -> list[tuple[list[str], list[list]]]:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True, keep_links=False)
    try:
        result = []
        for sheet in workbook.worksheets:
            if normalize_label(sheet.title or "") in SKIP_SHEETS:
                continue
            iterator = sheet.iter_rows(values_only=True)
            try:
                header = next(iterator)
            except StopIteration:
                continue
            headers = [str(item).strip() if item is not None else "" for item in header]
            if not any(headers):
                continue
            data = []
            for row in iterator:
                values = [None if item is None else str(item).strip() for item in row]
                if any(values):
                    data.append(values)
            if data:
                result.append((headers, data))
        return result
    finally:
        workbook.close()


def _csv_rows(content: bytes) -> list[tuple[list[str], list[list]]]:
    text = content.decode("utf-8-sig")
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    header = next(reader, None)
    if not header:
        return []
    data = [row for row in reader if any(cell.strip() for cell in row)]
    return [(header, data)]


def _key(name: str) -> str:
    return normalize_label(name)


def _cell(row: list, index: dict[str, int], aliases: set[str]) -> str | None:
    for alias in aliases:
        pos = index.get(normalize_label(alias))
        if pos is not None and pos < len(row) and row[pos]:
            return str(row[pos]).strip()
    return None


def _date(raw: str | None) -> date | None:
    if not raw:
        return None
    text = raw.strip()[:10]
    for fmt in ("%Y-%m-%d", "%Y-%m", "%d.%m.%Y"):
        try:
            parsed = datetime.strptime(text if fmt != "%Y-%m" else text[:7], fmt if fmt != "%Y-%m" else "%Y-%m")
            return date(parsed.year, parsed.month, 1 if fmt == "%Y-%m" else parsed.day)
        except ValueError:
            continue
    return None
