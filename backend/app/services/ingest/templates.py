"""Шаблоны файла загрузки CSV и XLSX."""

import csv
import io
from datetime import date

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from app.models import Indicator


def csv_template(indicators: list[Indicator]) -> bytes:
    codes = [item.code for item in indicators]
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["period", *codes])
    start = date(2024, 1, 1)
    for month in range(3):
        writer.writerow([_shift_month(start, month).strftime("%Y-%m"), *([""] * len(codes))])
    return buffer.getvalue().encode("utf-8-sig")


def xlsx_template(indicators: list[Indicator]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Данные"
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1F4E79")
    headers = ["period", *[item.code for item in indicators]]
    sheet.append(headers)
    for column, _ in enumerate(headers, start=1):
        cell = sheet.cell(1, column)
        cell.font = header_font
        cell.fill = header_fill
    start = date(2024, 1, 1)
    for month in range(3):
        sheet.append([_shift_month(start, month).strftime("%Y-%m")])
    for column, indicator in enumerate(indicators, start=2):
        sheet.column_dimensions[get_column_letter(column)].width = max(14, len(indicator.code) + 2)
    sheet.column_dimensions["A"].width = 12
    legend = workbook.create_sheet("Показатели")
    legend.append(["code", "name", "unit", "group", "impact_direction"])
    for item in indicators:
        legend.append([item.code, item.name, item.unit.code, item.group.code, item.impact_direction.value])
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _shift_month(start: date, offset: int) -> date:
    month = start.month + offset
    year = start.year + (month - 1) // 12
    return date(year, (month - 1) % 12 + 1, 1)
