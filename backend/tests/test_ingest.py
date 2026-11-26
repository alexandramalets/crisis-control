"""Проверка чтения и качества файлов без обращения к СУБД."""

import io
from datetime import date

import pytest
from openpyxl import Workbook

from app.services.errors import PayloadTooLargeError, ValidationFailedError
from app.services.ingest.file_reader import read_table
from app.services.ingest.filenames import original_filename
from app.services.ingest.indicators import IndicatorCatalog
from app.services.ingest.preprocessor import inspect_table, parse_table, quality_summary


class _Indicator:
    def __init__(self, code, name):
        self.code, self.name = code, name


CATALOG = IndicatorCatalog([
    _Indicator("revenue", "Выручка"),
    _Indicator("profit", "Прибыль"),
    _Indicator("receivables", "Дебиторская задолженность"),
    _Indicator("payables", "Кредиторская задолженность"),
    _Indicator("cash", "Денежные средства"),
    _Indicator("sales_volume", "Объём продаж"),
    _Indicator("inventory", "Запасы"),
])


def _csv(text: str, name="data.csv") -> bytes:
    return text.encode("utf-8")


def _xlsx(rows: list[list], name="data.xlsx") -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_filename_strips_path_traversal():
    assert original_filename("../../etc/passwd.csv") == "passwd.csv"
    assert original_filename("C:\\\\uploads\\\\file.xlsx") == "file.xlsx"
    assert original_filename("..\\..\\secret.csv") == "secret.csv"
    assert original_filename("folder/../../etc/passwd") == "passwd"
    assert original_filename("a\x00b.csv") == "ab.csv"
    assert original_filename(None) == "upload"
    assert original_filename("отчёт 2024.csv") == "отчёт 2024.csv"


def test_read_csv_and_preview_columns():
    table = read_table(_csv("period,revenue,profit\n2024-01,100,10\n2024-02,200,\n"), "report.csv",
                       max_bytes=10_000, max_rows=100)
    inspection = inspect_table(table, CATALOG)

    assert inspection["suggested_period_column"] == "period"
    assert {i["code"] for i in inspection["suggested_indicators"]} == {"revenue", "profit"}
    assert inspection["preview"][0]["revenue"] == "100"
    assert inspection["time_analysis"]["possible"] is False  # только 2 периода


def test_read_xlsx():
    table = read_table(_xlsx([["period", "Выручка"], ["2024-01", 1500], ["2024-02", 1600], ["2024-03", 1700]]),
                       "book.xlsx", max_bytes=50_000, max_rows=100)
    inspection = inspect_table(table, CATALOG)
    assert inspection["source_format"] == "xlsx"
    assert inspection["suggested_indicators"][0]["code"] == "revenue"
    assert inspection["time_analysis"]["possible"] is True


def test_empty_file():
    with pytest.raises(ValidationFailedError) as error:
        read_table(b"", "empty.csv", max_bytes=1000, max_rows=10)
    assert error.value.code == "empty_file"


def test_header_only_file():
    with pytest.raises(ValidationFailedError) as error:
        read_table(_csv("period,revenue\n"), "empty.csv", max_bytes=1000, max_rows=10)
    assert "не содержит строк" in error.value.message


def test_unsupported_format():
    with pytest.raises(ValidationFailedError) as error:
        read_table(b"%PDF-1.7", "notes.pdf", max_bytes=1000, max_rows=10)
    assert error.value.code == "unsupported_format"


def test_mismatched_extension():
    with pytest.raises(ValidationFailedError):
        read_table(_csv("period,revenue\n2024-01,1\n"), "data.xlsx", max_bytes=1000, max_rows=10)


def test_too_large():
    with pytest.raises(PayloadTooLargeError):
        read_table(b"a" * 50, "data.csv", max_bytes=10, max_rows=10)


def test_missing_and_invalid_and_duplicates():
    table = read_table(_csv(
        "period,revenue,profit\n"
        "2024-01,100,10\n"
        "2024-02,,20\n"
        "2024-03,abc,30\n"
        "2024-01,100,10\n"
        "не-дата,1,1\n"
    ), "bad.csv", max_bytes=10_000, max_rows=100)
    result = parse_table(table, CATALOG, period_column="period", indicator_columns=["revenue", "profit"],
                         category_column=None, granularity=None)
    summary = quality_summary(result, table)

    assert result.ready_for_save is False
    assert summary["missing_count"] >= 1
    assert summary["invalid_number_count"] >= 1
    assert summary["invalid_period_count"] >= 1
    assert summary["duplicate_count"] >= 1


def test_subset_of_indicators_is_enough():
    table = read_table(_csv("period,revenue\n2023-01,1\n2023-02,2\n2023-03,3\n"), "small.csv",
                       max_bytes=1000, max_rows=100)
    result = parse_table(table, CATALOG, period_column=None, indicator_columns=None,
                         category_column=None, granularity=None)
    assert result.ready_for_save
    assert {c.indicator_code for c in result.cells} == {"revenue"}
    assert result.cells[0].period_start == date(2023, 1, 1)


def test_no_numeric_indicator_columns():
    table = read_table(_csv("period,comment\n2024-01,ok\n2024-02,ok\n"), "text.csv",
                       max_bytes=1000, max_rows=100)
    with pytest.raises(ValidationFailedError) as error:
        parse_table(table, CATALOG, period_column="period", indicator_columns=None,
                    category_column=None, granularity=None)
    assert error.value.code == "no_numeric_columns"


def test_invalid_period_column_message():
    table = read_table(_csv("period,revenue\n2024-01,1\n"), "ok.csv", max_bytes=1000, max_rows=100)
    with pytest.raises(ValidationFailedError) as error:
        parse_table(table, CATALOG, period_column="missing", indicator_columns=["revenue"],
                    category_column=None, granularity=None)
    assert "временн" in error.value.message


def test_decimal_comma_is_recorded_not_silent():
    table = read_table(_csv("period,revenue\n2024-01,\"1 234,50\"\n2024-02,2\n2024-03,3\n"), "ru.csv",
                       max_bytes=1000, max_rows=100)
    result = parse_table(table, CATALOG, period_column="period", indicator_columns=["revenue"],
                         category_column=None, granularity=None)
    assert result.ready_for_save
    assert result.cells[0].value == __import__("decimal").Decimal("1234.50")
    assert any(t.code == "decimal_separator_normalized" for t in result.transformations)


def test_xlsx_merges_indicator_sheets_by_period():
    workbook = Workbook()
    first = workbook.active
    first.title = "Выручка"
    first.append(["period", "revenue"])
    first.append(["2024-01", 100])
    first.append(["2024-02", 110])
    second = workbook.create_sheet("Касса")
    second.append(["period", "cash"])
    second.append(["2024-01", 50])
    second.append(["2024-02", 55])
    second.append(["2024-03", 60])
    workbook.create_sheet("Описание").append(["текст"])
    buffer = io.BytesIO()
    workbook.save(buffer)
    table = read_table(buffer.getvalue(), "many.xlsx", max_bytes=50_000, max_rows=100)
    result = parse_table(table, CATALOG, period_column=None, indicator_columns=None,
                         category_column=None, granularity=None)
    assert result.ready_for_save
    codes = {cell.indicator_code for cell in result.cells}
    assert codes == {"revenue", "cash"}
    periods = {cell.period_start for cell in result.cells}
    assert date(2024, 3, 1) in periods
