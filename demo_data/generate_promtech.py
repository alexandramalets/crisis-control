"""Генератор демонстрационного кейса ООО «ПромТехСервис».

Запуск из каталога backend (нужен openpyxl) или из корня проекта:
    python demo_data/generate_promtech.py
"""

from __future__ import annotations

import csv
import math
import sys
from datetime import date
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill, numbers
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent
SEED_NOTE = "Вымышленные данные для демонстрации Crisis Control. Не относятся к реальной организации."

# Только исходные показатели справочника. Коэффициенты считает программа.
COLUMNS = [
    "period",
    "revenue",
    "sales_volume",
    "output",
    "cogs",
    "profit",
    "net_profit",
    "receivables",
    "overdue_receivables",
    "payables",
    "inventory",
    "cash",
    "current_assets",
    "current_liabilities",
    "long_term_debt",
    "equity",
    "total_assets",
    "cf_operating",
    "cf_investing",
    "cf_financing",
    "personnel",
]

RU_HEADERS = {
    "period": "period",
    "revenue": "Выручка",
    "sales_volume": "Объём продаж",
    "output": "Объём производства",
    "cogs": "Себестоимость",
    "profit": "Прибыль",
    "net_profit": "Чистая прибыль",
    "receivables": "Дебиторская задолженность",
    "overdue_receivables": "Просроченная дебиторская задолженность",
    "payables": "Кредиторская задолженность",
    "inventory": "Запасы",
    "cash": "Денежные средства",
    "current_assets": "Оборотные активы",
    "current_liabilities": "Краткосрочные обязательства",
    "long_term_debt": "Долгосрочные обязательства",
    "equity": "Собственный капитал",
    "total_assets": "Активы",
    "cf_operating": "Денежный поток от операционной деятельности",
    "cf_investing": "Денежный поток от инвестиционной деятельности",
    "cf_financing": "Денежный поток от финансовой деятельности",
    "personnel": "Численность персонала",
}

DATASET_NAME = "ПромТехСервис 2023–2025"


def month_start(index: int) -> date:
    year, month = divmod(index, 12)
    return date(2023 + year, month + 1, 1)


def stress_initial(t: int) -> float:
    """0 — стабильность (2023), рост проблем в 2024, пик к сентябрю 2025, слабое облегчение к декабрю."""
    if t < 12:
        return 0.02 * (t / 11)
    if t < 24:
        return 0.08 + 0.42 * ((t - 12) / 11)
    if t < 33:
        return 0.50 + 0.50 * ((t - 24) / 8)
    return 0.92 - 0.12 * ((t - 32) / 3)


def stress_recovery(t: int) -> float:
    """Та же история до конца 2024, с 2025 — меры: проблемы снижаются, но не исчезают."""
    if t < 24:
        return stress_initial(t) * 0.92
    if t < 33:
        peak = 0.62
        return 0.48 + (peak - 0.48) * ((t - 24) / 8) * 0.55
    return 0.38 - 0.10 * ((t - 32) / 3)


def seasonal(t: int) -> float:
    return 1.0 + 0.07 * math.sin(2 * math.pi * (t - 2) / 12)


def r(value: float) -> float:
    return float(round(value, 2))


def ri(value: float) -> int:
    return int(round(value))


def cash_target(t: int, mode: str) -> float:
    """Явный путь остатка денег: в кризисе сжимается, после мер восстанавливается не полностью."""
    if t < 12:
        return 16_800_000 + 180_000 * t
    if t < 24:
        return 18_800_000 - 420_000 * (t - 11)
    if mode == "initial":
        if t < 33:
            return 13_400_000 - 780_000 * (t - 23)
        if t == 33:
            return 6_900_000
        if t == 34:
            return 7_150_000
        return 6_420_000
    if t < 33:
        return 13_400_000 - 280_000 * (t - 23)
    return 11_200_000 + 420_000 * (t - 32)


def build_series(mode: str) -> list[dict]:
    stress_fn = stress_initial if mode == "initial" else stress_recovery
    rows: list[dict] = []
    equity = 78_500_000.0
    ltd = 16_400_000.0
    nca = 52_000_000.0
    personnel = 186.0
    rec_prev = inv_prev = pay_prev = None

    for t in range(36):
        s = stress_fn(t)
        sea = seasonal(t)
        period = month_start(t)

        trend = 1 + 0.0065 * min(t, 11)
        if t >= 12:
            trend *= 1 - 0.004 * (t - 11) * min(1.0, s + 0.2)
        revenue = 34_800_000 * trend * sea * (1 - 0.16 * s)
        if mode == "initial" and t == 26:
            revenue *= 0.64
        if mode == "recovery" and t >= 24:
            revenue *= 1 + 0.035 * (t - 23) / 12

        price = 88_500 * (1 + 0.0012 * t)
        sales_volume = revenue / price
        output = sales_volume * (1.015 + 0.07 * s)

        cogs = revenue * (0.635 + 0.09 * s)
        if mode == "initial" and t == 30:
            cogs *= 1.20
        opex = revenue * (0.155 + 0.05 * s)
        profit = revenue - cogs - opex
        interest = 210_000 + 390_000 * s
        tax = max(0.0, profit - interest) * 0.20
        net_profit = profit - interest - tax

        receivables = revenue * ((36 + 48 * s) / 30)
        if mode == "initial" and t == 28:
            receivables *= 1.62
        if mode == "recovery" and t >= 24:
            receivables *= 1 - 0.16 * (t - 23) / 12
        overdue = receivables * (0.055 + 0.20 * s)

        inventory = cogs * ((40 + 36 * s) / 30)
        if mode == "recovery" and t >= 24:
            inventory *= 1 - 0.12 * (t - 23) / 12

        payables = cogs * ((30 + 26 * s) / 30)
        if mode == "initial" and t == 35:
            payables *= 1.06

        personnel = 186 + 0.4 * min(t, 18) - (0.9 * max(0, t - 24) if s > 0.4 else 0)
        personnel = max(176, min(198, personnel))

        cash = cash_target(t, mode)
        other_ca = 2_600_000 + 25_000 * t
        current_assets = cash + receivables + inventory + other_ca

        if s < 0.3:
            ltd = max(14_800_000, ltd - 60_000)
        else:
            ltd += 140_000 * s
        if mode == "recovery" and t >= 24:
            ltd = max(15_000_000, ltd - 110_000)

        st_debt = 5_800_000 + 8_600_000 * s
        if mode == "recovery" and t >= 24:
            st_debt *= 0.84
        if mode == "initial" and t == 35:
            st_debt *= 1.05
        current_liabilities = payables + st_debt

        equity = equity + net_profit
        equity = max(equity, current_assets * 0.15)
        total_assets = equity + current_liabilities + ltd
        nca = total_assets - current_assets
        if nca < 28_000_000:
            nca = 28_000_000
            total_assets = current_assets + nca
            equity = total_assets - current_liabilities - ltd

        capex = 480_000 * (1 - 0.5 * max(0, s - 0.4))
        cf_investing = -capex
        if rec_prev is None:
            delta_wc = 0.0
        else:
            delta_wc = (receivables - rec_prev) + (inventory - inv_prev) - (payables - pay_prev)
        cf_operating = net_profit + 220_000 - delta_wc
        if mode == "initial" and t in {26, 30}:
            cf_operating -= 2_400_000
        if mode == "initial" and t == 35:
            cf_operating -= 1_100_000

        row = {
            "period": period.strftime("%Y-%m"),
            "revenue": r(revenue),
            "sales_volume": r(sales_volume),
            "output": r(output),
            "cogs": r(cogs),
            "profit": r(profit),
            "net_profit": r(net_profit),
            "receivables": r(receivables),
            "overdue_receivables": r(min(overdue, receivables)),
            "payables": r(payables),
            "inventory": r(inventory),
            "cash": r(cash),
            "current_assets": r(current_assets),
            "current_liabilities": r(current_liabilities),
            "long_term_debt": r(ltd),
            "total_assets": r(total_assets),
            "equity": r(equity),
            "personnel": ri(personnel),
            "cf_operating": r(cf_operating),
            "cf_investing": r(cf_investing),
        }
        row["equity"] = r(row["total_assets"] - row["current_liabilities"] - row["long_term_debt"])
        if t == 0:
            row["cf_financing"] = r(0.0)
            # первая точка: потоки ещё не связываем с предыдущей кассой
            row["cf_operating"] = r(max(row["profit"] * 0.4, 400_000))
            row["cf_financing"] = r(-row["cf_operating"] - row["cf_investing"])
        else:
            row["cf_financing"] = r(
                row["cash"] - rows[-1]["cash"] - row["cf_operating"] - row["cf_investing"]
            )
        parts = row["cash"] + row["receivables"] + row["inventory"]
        if row["current_assets"] + 0.01 < parts:
            row["current_assets"] = r(parts + other_ca)
            row["total_assets"] = r(row["current_assets"] + nca)
            row["equity"] = r(row["total_assets"] - row["current_liabilities"] - row["long_term_debt"])

        rows.append(row)
        rec_prev, inv_prev, pay_prev = receivables, inventory, payables
        equity = row["equity"]
        ltd = row["long_term_debt"]

    return rows


def assert_consistent(rows: list[dict], label: str) -> list[str]:
    problems = []
    for i, row in enumerate(rows):
        p = row["period"]
        if row["receivables"] < 0 or row["inventory"] < 0 or row["cash"] < 0 or row["payables"] < 0:
            problems.append(f"{label} {p}: отрицательный остаток")
        if row["overdue_receivables"] - row["receivables"] > 0.01:
            problems.append(f"{label} {p}: просрочка больше дебиторки")
        if row["payables"] - row["current_liabilities"] > 0.01:
            problems.append(f"{label} {p}: кредиторка больше краткосрочных обязательств")
        identity = row["equity"] + row["current_liabilities"] + row["long_term_debt"]
        if abs(identity - row["total_assets"]) > 0.05:
            problems.append(f"{label} {p}: баланс {identity} ≠ {row['total_assets']}")
        if row["current_assets"] > row["total_assets"] + 0.05:
            problems.append(f"{label} {p}: оборотные > активы")
        if row["cash"] + row["receivables"] + row["inventory"] - row["current_assets"] > 1:
            problems.append(f"{label} {p}: сумма CA-частей больше оборотных")
        if i:
            walk = rows[i - 1]["cash"] + row["cf_operating"] + row["cf_investing"] + row["cf_financing"]
            if abs(walk - row["cash"]) > 0.05:
                problems.append(f"{label} {p}: касса не сходится с потоками ({walk} vs {row['cash']})")
        if row["sales_volume"] <= 0 or row["output"] <= 0 or row["personnel"] <= 0:
            problems.append(f"{label} {p}: неположительный операционный показатель")
    return problems


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def mad_z(values: list[float], index: int) -> float:
    med = _median(values)
    deviations = [abs(v - med) for v in values]
    scale = _median(deviations) * 1.4826
    if scale == 0:
        return 0.0
    return abs(values[index] - med) / scale


def ratio_last(rows: list[dict]) -> dict[str, float | None]:
    a = rows[-1]
    def div(n, d):
        return None if d == 0 else n / d
    return {
        "current_ratio": div(a["current_assets"], a["current_liabilities"]),
        "quick_ratio": div(a["current_assets"] - a["inventory"], a["current_liabilities"]),
        "cash_ratio": div(a["cash"], a["current_liabilities"]),
        "autonomy": div(a["equity"], a["total_assets"]),
        "debt_to_equity": div(a["current_liabilities"] + a["long_term_debt"], a["equity"]),
        "working_capital_ratio": div(
            a["equity"] - (a["total_assets"] - a["current_assets"]), a["current_assets"],
        ),
        "ros": None if not a["revenue"] else a["profit"] / a["revenue"] * 100,
        "roa": None if not a["total_assets"] else a["profit"] / a["total_assets"] * 100,
        "roe": None if not a["equity"] else a["profit"] / a["equity"] * 100,
        "receivables_turnover": div(a["revenue"], a["receivables"]),
        "inventory_turnover": div(a["cogs"], a["inventory"]),
        "asset_turnover": div(a["revenue"], a["total_assets"]),
        "debt_to_capital": div(
            a["current_liabilities"] + a["long_term_debt"],
            a["equity"] + a["current_liabilities"] + a["long_term_debt"],
        ),
        "debt_to_assets": div(a["current_liabilities"] + a["long_term_debt"], a["total_assets"]),
        "cash_coverage": div(a["cf_operating"], a["current_liabilities"]),
    }


def last_findings(rows: list[dict]) -> list[str]:
    sys.path.insert(0, str(ROOT.parent / "backend"))
    from app.services.crisis_engine import build_findings, recommendations_for

    values = {code: [row[code] for row in rows] for code in COLUMNS if code != "period"}
    directions = {
        "cash": "higher_better", "payables": "lower_better", "receivables": "lower_better",
        "revenue": "higher_better", "profit": "higher_better", "cogs": "lower_better",
        "cf_operating": "higher_better", "equity": "higher_better",
    }

    def ratio(code, last, prev):
        pct = None if prev in (0, None) or last is None else 100.0 * (last - prev) / abs(prev)
        return {"code": code, "last_value": last, "pct_change": pct}

    a, b = rows[-1], rows[-2]
    cr_a = a["current_assets"] / a["current_liabilities"]
    cr_b = b["current_assets"] / b["current_liabilities"]
    auto_a = a["equity"] / a["total_assets"]
    auto_b = b["equity"] / b["total_assets"]
    dte_a = (a["current_liabilities"] + a["long_term_debt"]) / a["equity"]
    dte_b = (b["current_liabilities"] + b["long_term_debt"]) / b["equity"]
    ros_a = 100 * a["profit"] / a["revenue"]
    ros_b = 100 * b["profit"] / b["revenue"]
    to_a = a["revenue"] / a["receivables"]
    to_b = b["revenue"] / b["receivables"]
    ratios = [
        ratio("current_ratio", cr_a, cr_b),
        ratio("autonomy", auto_a, auto_b),
        ratio("debt_to_equity", dte_a, dte_b),
        ratio("ros", ros_a, ros_b),
        ratio("receivables_turnover", to_a, to_b),
    ]
    findings = build_findings(values=values, directions=directions, ratios=ratios, period=a["period"])
    recs = recommendations_for(findings)
    return [f"{item['code']}/{item['confidence']}/{item['severity']}" for item in findings] + [
        f"reco:{item['finding_code']}" for item in recs
    ]


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle, delimiter=";")
        writer.writerow([RU_HEADERS[c] if c != "period" else "period" for c in COLUMNS])
        for row in rows:
            writer.writerow([row[c] for c in COLUMNS])


def _header_fill(sheet, headers):
    font = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="1F4E79")
    sheet.append(headers)
    for col in range(1, len(headers) + 1):
        cell = sheet.cell(1, col)
        cell.font = font
        cell.fill = fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        sheet.column_dimensions[get_column_letter(col)].width = 18
    sheet.row_dimensions[1].height = 28
    sheet.freeze_panes = "B2"
    sheet.auto_filter.ref = sheet.dimensions


def write_xlsx(path: Path, rows: list[dict], title: str) -> None:
    book = Workbook()
    sheet = book.active
    sheet.title = "Данные"
    headers = ["period"] + [RU_HEADERS[c] for c in COLUMNS if c != "period"]
    _header_fill(sheet, headers)
    money = [c for c in COLUMNS if c not in {"period", "sales_volume", "output", "personnel"}]
    for row in rows:
        values = [row["period"]] + [row[c] for c in COLUMNS if c != "period"]
        sheet.append(values)
        r_idx = sheet.max_row
        for col, code in enumerate(COLUMNS, start=1):
            cell = sheet.cell(r_idx, col)
            if code == "period":
                continue
            if code in {"sales_volume", "output"}:
                cell.number_format = "#,##0.00"
            elif code == "personnel":
                cell.number_format = "0"
            elif code in money:
                cell.number_format = "#,##0.00"
    info = book.create_sheet("Описание")
    info.append(["Поле", "Значение"])
    info.append(["Организация", "ООО «ПромТехСервис»"])
    info.append(["Набор", DATASET_NAME])
    info.append(["Вариант", title])
    info.append(["Период", "2023-01 … 2025-12"])
    info.append(["Периодичность", "месяц"])
    info.append(["Примечание", SEED_NOTE])
    info.append(["Коэффициенты", "Не входят в файл — считает Crisis Control"])
    book.save(path)


def write_quality_xlsx(path: Path) -> None:
    book = Workbook()
    sheet = book.active
    sheet.title = "Данные"
    sheet.append(["period", "Выручка", "Запасы", "Денежные средства"])
    sheet.append(["2024-01", 10_000_000, 4_000_000, 2_000_000])
    sheet.append(["2024-01", 11_000_000, 4_100_000, 2_100_000])  # дубль периода
    sheet.append(["2024-13", 9_000_000, 3_800_000, 1_900_000])  # некорректная дата
    sheet.append(["2024-03-15", 9_500_000, 3_900_000, 1_850_000])  # не начало месяца
    sheet.append(["2024-04", "нет числа", 4_000_000, 1_800_000])  # текст в числе
    sheet.append(["2024-05", 8_000_000, -250_000, None])  # отрицательные запасы и пропуск кассы
    book.save(path)


def write_norms_xlsx(path: Path) -> None:
    book = Workbook()
    plans = book.active
    plans.title = "Планы"
    _header_fill(plans, [
        "indicator_code", "Показатель", "Тип", "Значение", "Единица",
        "valid_from", "valid_to", "Источник", "Описание",
    ])
    items = [
        ("revenue", "Выручка", "plan", 52_000_000, "руб./мес.", "2025-01-01", "2025-12-01",
         "Бюджет ООО «ПромТехСервис» на 2025 год", "Целевой объём продаж оборудования"),
        ("profit", "Прибыль", "plan", 6_200_000, "руб./мес.", "2025-01-01", "2025-12-01",
         "Бюджет ООО «ПромТехСервис» на 2025 год", "Целевая прибыль от продаж"),
        ("cash", "Денежные средства", "target", 12_000_000, "руб.", "2025-01-01", "2025-12-01",
         "Платёжная политика организации", "Минимально комфортный остаток на счетах"),
        ("receivables", "Дебиторская задолженность", "norm", 28_000_000, "руб.", "2025-01-01", "2025-12-01",
         "Регламент расчётов с покупателями", "Допустимый остаток задолженности покупателей"),
        ("current_ratio", "Текущая ликвидность", "target", 1.5, "коэфф.", "2025-01-01", "2025-12-01",
         "Внутренний финансовый регламент", "Целевой коэффициент текущей ликвидности"),
        ("autonomy", "Коэффициент автономии", "target", 0.4, "коэфф.", "2025-01-01", "2025-12-01",
         "Внутренний финансовый регламент", "Доля собственного капитала в активах"),
        ("ros", "Рентабельность продаж", "plan", 12, "%", "2025-01-01", "2025-12-01",
         "Бюджет ООО «ПромТехСервис» на 2025 год", "Целевая рентабельность продаж"),
    ]
    for item in items:
        plans.append(list(item))

    bounds = book.create_sheet("Границы")
    _header_fill(bounds, [
        "indicator_code", "Показатель", "Нижняя", "Верхняя", "Единица",
        "Источник", "Методика",
    ])
    for row in [
        ("cash", "Денежные средства", 8_000_000, None, "руб.",
         "Платёжная политика организации", "Ниже границы — риск кассового разрыва; не отраслевой норматив"),
        ("receivables", "Дебиторская задолженность", None, 45_000_000, "руб.",
         "Регламент расчётов", "Верхняя граница допустимой задолженности покупателей"),
        ("current_ratio", "Текущая ликвидность", 1.0, None, "коэфф.",
         "Внутренний финансовый регламент", "Ниже 1 оборотные активы не покрывают краткосрочные обязательства"),
        ("overdue_receivables", "Просроченная дебиторская задолженность", None, 8_000_000, "руб.",
         "Регламент расчётов", "Контроль просрочки"),
    ]:
        bounds.append(list(row))

    measures = book.create_sheet("Мероприятия_для_интерфейса")
    _header_fill(measures, [
        "Название", "Описание", "Приоритет", "Срок", "Ответственный",
        "Ожидаемый результат", "Критерий выполнения",
    ])
    for row in [
        ("Ускорить взыскание дебиторской задолженности",
         "Разбор реестра покупателей, претензионная работа по просрочке свыше 30 дней.",
         "high", "2026-02-28", "Начальник отдела сбыта",
         "Сокращение просроченной дебиторской задолженности",
         "Просрочка ниже 8 млн руб. по итогам двух месяцев"),
        ("Нормировать склад незавершённого производства и комплектующих",
         "Пересмотр страховых запасов и графика закупок сырья.",
         "medium", "2026-03-31", "Начальник производства",
         "Снижение замороженных оборотных средств",
         "Оборачиваемость запасов выше уровня декабря 2024"),
        ("Сжать административные и накладные расходы",
         "Пересмотр постоянных затрат без остановки основного выпуска.",
         "high", "2026-01-31", "Финансовый директор",
         "Восстановление маржи",
         "Прибыль от продаж положительная два месяца подряд"),
        ("Календарь платежей и лимит краткосрочного долга",
         "Сопоставить поступления и погашение краткосрочных обязательств.",
         "high", "2026-01-15", "Главный бухгалтер",
         "Снижение давления на ликвидность",
         "Остаток денежных средств устойчиво выше 8 млн руб."),
    ]:
        measures.append(list(row))

    note = book.create_sheet("Как_внести")
    note.append(["Листы «Планы» и «Границы» загружаются в разделе «Нормативы». Лист мероприятий вводится вручную."])
    note.append(["Раздел «Нормативы»: код показателя, тип (план/норматив/цель), значение, источник."])
    note.append(["Границы: нижняя и/или верхняя, источник и методика."])
    note.append(["Мероприятия создаются после исследования: из рекомендации или формой на странице «Мероприятия»."])
    book.save(path)


def parse_with_app(path: Path) -> dict:
    sys.path.insert(0, str(ROOT.parent / "backend"))
    from types import SimpleNamespace

    from app.services.ingest.file_reader import read_table
    from app.services.ingest.indicators import IndicatorCatalog
    from app.services.ingest.preprocessor import parse_table, quality_summary

    catalog = IndicatorCatalog([
        SimpleNamespace(code=code, name=RU_HEADERS[code])
        for code in COLUMNS if code != "period"
    ])
    content = path.read_bytes()
    table = read_table(content, path.name, max_bytes=10_000_000, max_rows=500)
    result = parse_table(
        table, catalog, period_column="period", indicator_columns=None,
        category_column=None, granularity=None,
    )
    summary = quality_summary(result, table)
    return {"ready": result.ready_for_save, "summary": summary, "errors": [
        item.message for item in result.issues if item.severity.value == "error"
    ], "mapped": result.indicator_columns}


def main() -> int:
    initial = build_series("initial")
    recovery = build_series("recovery")
    problems = assert_consistent(initial, "initial") + assert_consistent(recovery, "recovery")
    if problems:
        print("Ошибки согласованности:")
        for item in problems:
            print(" -", item)
        return 1

    write_xlsx(ROOT / "promtech_service_initial.xlsx", initial, "исходная история")
    write_xlsx(ROOT / "promtech_service_recovery.xlsx", recovery, "после антикризисных мер")
    write_csv(ROOT / "promtech_service_initial.csv", initial)
    write_csv(ROOT / "promtech_service_recovery.csv", recovery)
    write_quality_xlsx(ROOT / "promtech_service_quality_test.xlsx")
    write_norms_xlsx(ROOT / "promtech_service_norms.xlsx")

    findings = last_findings(initial)
    print("Строк:", len(initial), "показателей:", len(COLUMNS) - 1)
    print("Проблемы на 2025-12 (исходный набор):", findings or "нет")
    print("Коэффициенты на 2025-12:")
    for code, value in ratio_last(initial).items():
        print(f"  {code}: {None if value is None else round(value, 3)}")
    rev = [row["revenue"] for row in initial]
    rec = [row["receivables"] for row in initial]
    profit = [row["profit"] for row in initial]
    print("MAD z выручка 2025-03:", round(mad_z(rev, 26), 2))
    print("MAD z дебиторка 2025-05:", round(mad_z(rec, 28), 2))
    print("MAD z прибыль 2025-07:", round(mad_z(profit, 30), 2))
    print("Выручка 2023-01 / 2024-12 / 2025-09 / 2025-12:",
          initial[0]["revenue"], initial[23]["revenue"], initial[32]["revenue"], initial[35]["revenue"])
    print("Касса 2023-01 / 2025-09 / 2025-12:",
          initial[0]["cash"], initial[32]["cash"], initial[35]["cash"])
    print("Касса recovery 2025-12:", recovery[35]["cash"], "исходный:", initial[35]["cash"])

    for name in ("promtech_service_initial.xlsx", "promtech_service_initial.csv",
                 "promtech_service_recovery.xlsx"):
        report = parse_with_app(ROOT / name)
        print(name, "ready=", report["ready"], "mapped=", len(report["mapped"]),
              "errors=", len(report["errors"]))
        if not report["ready"]:
            for err in report["errors"][:8]:
                print("  ", err)
            return 1

    bad = parse_with_app(ROOT / "promtech_service_quality_test.xlsx")
    print("quality_test ready=", bad["ready"], "errors=", len(bad["errors"]))
    if bad["ready"]:
        print("Файл с ошибками не должен проходить сохранение")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
