from decimal import Decimal

from openpyxl import Workbook
import io

from app.services.ingest.profile_import import parse_profile_file


def test_parse_norms_workbook():
    book = Workbook()
    plans = book.active
    plans.title = "Планы"
    plans.append(["indicator_code", "Тип", "Значение", "Источник"])
    plans.append(["revenue", "plan", 1000, "бюджет"])
    bounds = book.create_sheet("Границы")
    bounds.append(["indicator_code", "Нижняя", "Верхняя", "Источник"])
    bounds.append(["cash", 100, None, "регламент"])
    buffer = io.BytesIO()
    book.save(buffer)
    parsed = parse_profile_file(buffer.getvalue(), "norms.xlsx")
    assert parsed["targets"][0]["indicator_code"] == "revenue"
    assert parsed["targets"][0]["kind"] == "plan"
    assert parsed["targets"][0]["value"] == Decimal("1000")
    assert parsed["thresholds"][0]["indicator_code"] == "cash"
    assert parsed["thresholds"][0]["lower_bound"] == Decimal("100")


def test_parse_skips_instruction_sheets():
    book = Workbook()
    plans = book.active
    plans.title = "Планы"
    plans.append(["indicator_code", "Тип", "Значение"])
    plans.append(["profit", "plan", 10])
    note = book.create_sheet("Как_внести")
    note.append(["Это не таблица нормативов"])
    note.append(["Не должно попасть в разбор"])
    measures = book.create_sheet("Мероприятия_для_интерфейса")
    measures.append(["Название", "Описание"])
    measures.append(["Работа с дебиторкой", "Текст"])
    buffer = io.BytesIO()
    book.save(buffer)
    parsed = parse_profile_file(buffer.getvalue(), "norms.xlsx")
    assert len(parsed["targets"]) == 1
    assert parsed["targets"][0]["indicator_code"] == "profit"
    assert parsed["thresholds"] == []
