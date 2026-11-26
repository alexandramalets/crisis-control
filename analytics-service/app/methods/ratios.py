"""Производные финансово-экономические коэффициенты. Не подставляет нули вместо пропусков."""

from app.methods.frame import AnalysisFrame
from app.methods.result import procedure, skipped
from app.schemas.common import ProcedureResult

# formula uses codes present in the frame; skip if any input is missing at the period.
CATALOG = [
    {
        "code": "current_ratio",
        "name": "Текущая ликвидность",
        "category": "liquidity",
        "formula": "current_assets / current_liabilities",
        "inputs": ["current_assets", "current_liabilities"],
        "unit": "ratio",
        "direction": "higher_better",
        "zero_denominators": "skip",
    },
    {
        "code": "quick_ratio",
        "name": "Быстрая ликвидность",
        "category": "liquidity",
        "formula": "(current_assets - inventory) / current_liabilities",
        "inputs": ["current_assets", "inventory", "current_liabilities"],
        "unit": "ratio",
        "direction": "higher_better",
        "zero_denominators": "skip",
    },
    {
        "code": "cash_ratio",
        "name": "Абсолютная ликвидность",
        "category": "liquidity",
        "formula": "cash / current_liabilities",
        "inputs": ["cash", "current_liabilities"],
        "unit": "ratio",
        "direction": "higher_better",
        "zero_denominators": "skip",
    },
    {
        "code": "autonomy",
        "name": "Коэффициент автономии",
        "category": "stability",
        "formula": "equity / total_assets",
        "inputs": ["equity", "total_assets"],
        "unit": "ratio",
        "direction": "higher_better",
        "zero_denominators": "skip",
    },
    {
        "code": "debt_to_equity",
        "name": "Заёмный капитал / собственный капитал",
        "category": "stability",
        "formula": "(current_liabilities + long_term_debt) / equity",
        "inputs": ["current_liabilities", "long_term_debt", "equity"],
        "unit": "ratio",
        "direction": "lower_better",
        "zero_denominators": "skip",
    },
    {
        "code": "working_capital_ratio",
        "name": "Обеспеченность собственными оборотными средствами",
        "category": "stability",
        "formula": "(equity - (total_assets - current_assets)) / current_assets",
        "inputs": ["equity", "total_assets", "current_assets"],
        "unit": "ratio",
        "direction": "higher_better",
        "zero_denominators": "skip",
    },
    {
        "code": "ros",
        "name": "Рентабельность продаж",
        "category": "profitability",
        "formula": "profit / revenue * 100",
        "inputs": ["profit", "revenue"],
        "unit": "pct",
        "direction": "higher_better",
        "zero_denominators": "skip",
        "scale": 100,
    },
    {
        "code": "roa",
        "name": "Рентабельность активов",
        "category": "profitability",
        "formula": "profit / total_assets * 100",
        "inputs": ["profit", "total_assets"],
        "unit": "pct",
        "direction": "higher_better",
        "zero_denominators": "skip",
        "scale": 100,
    },
    {
        "code": "roe",
        "name": "Рентабельность собственного капитала",
        "category": "profitability",
        "formula": "profit / equity * 100",
        "inputs": ["profit", "equity"],
        "unit": "pct",
        "direction": "higher_better",
        "zero_denominators": "skip",
        "scale": 100,
    },
    {
        "code": "receivables_turnover",
        "name": "Оборачиваемость дебиторской задолженности",
        "category": "activity",
        "formula": "revenue / receivables",
        "inputs": ["revenue", "receivables"],
        "unit": "ratio",
        "direction": "higher_better",
        "zero_denominators": "skip",
    },
    {
        "code": "inventory_turnover",
        "name": "Оборачиваемость запасов",
        "category": "activity",
        "formula": "cogs / inventory",
        "inputs": ["cogs", "inventory"],
        "unit": "ratio",
        "direction": "higher_better",
        "zero_denominators": "skip",
    },
    {
        "code": "asset_turnover",
        "name": "Оборачиваемость активов",
        "category": "activity",
        "formula": "revenue / total_assets",
        "inputs": ["revenue", "total_assets"],
        "unit": "ratio",
        "direction": "higher_better",
        "zero_denominators": "skip",
    },
    {
        "code": "debt_to_capital",
        "name": "Долг / капитал",
        "category": "debt",
        "formula": "(current_liabilities + long_term_debt) / (equity + current_liabilities + long_term_debt)",
        "inputs": ["current_liabilities", "long_term_debt", "equity"],
        "unit": "ratio",
        "direction": "lower_better",
        "zero_denominators": "skip",
    },
    {
        "code": "debt_to_assets",
        "name": "Долг / активы",
        "category": "debt",
        "formula": "(current_liabilities + long_term_debt) / total_assets",
        "inputs": ["current_liabilities", "long_term_debt", "total_assets"],
        "unit": "ratio",
        "direction": "lower_better",
        "zero_denominators": "skip",
    },
    {
        "code": "cash_coverage",
        "name": "Поступления / платежи (операционный поток к обязательствам)",
        "category": "cashflow",
        "formula": "cf_operating / current_liabilities",
        "inputs": ["cf_operating", "current_liabilities"],
        "unit": "ratio",
        "direction": "higher_better",
        "zero_denominators": "skip",
    },
]


def _eval(spec: dict, values: dict[str, float | None]) -> tuple[float | None, str | None]:
    missing = [code for code in spec["inputs"] if values.get(code) is None]
    if missing:
        return None, f"нет исходных данных: {', '.join(missing)}"
    nums = {code: float(values[code]) for code in spec["inputs"]}
    scale = float(spec.get("scale") or 1)
    try:
        if spec["code"] == "current_ratio":
            den = nums["current_liabilities"]
            if den == 0:
                return None, "знаменатель current_liabilities = 0, коэффициент не считается"
            return nums["current_assets"] / den * scale, None
        if spec["code"] == "quick_ratio":
            den = nums["current_liabilities"]
            if den == 0:
                return None, "знаменатель current_liabilities = 0"
            return (nums["current_assets"] - nums["inventory"]) / den * scale, None
        if spec["code"] == "cash_ratio":
            den = nums["current_liabilities"]
            if den == 0:
                return None, "знаменатель current_liabilities = 0"
            return nums["cash"] / den * scale, None
        if spec["code"] == "autonomy":
            den = nums["total_assets"]
            if den == 0:
                return None, "знаменатель total_assets = 0"
            return nums["equity"] / den * scale, None
        if spec["code"] == "debt_to_equity":
            den = nums["equity"]
            if den == 0:
                return None, "знаменатель equity = 0"
            return (nums["current_liabilities"] + nums["long_term_debt"]) / den * scale, None
        if spec["code"] == "working_capital_ratio":
            den = nums["current_assets"]
            if den == 0:
                return None, "знаменатель current_assets = 0"
            own_wc = nums["equity"] - (nums["total_assets"] - nums["current_assets"])
            return own_wc / den * scale, None
        if spec["code"] == "ros":
            den = nums["revenue"]
            if den == 0:
                return None, "знаменатель revenue = 0"
            return nums["profit"] / den * scale, None
        if spec["code"] == "roa":
            den = nums["total_assets"]
            if den == 0:
                return None, "знаменатель total_assets = 0"
            return nums["profit"] / den * scale, None
        if spec["code"] == "roe":
            den = nums["equity"]
            if den == 0:
                return None, "знаменатель equity = 0"
            return nums["profit"] / den * scale, None
        if spec["code"] == "receivables_turnover":
            den = nums["receivables"]
            if den == 0:
                return None, "знаменатель receivables = 0"
            return nums["revenue"] / den * scale, None
        if spec["code"] == "inventory_turnover":
            den = nums["inventory"]
            if den == 0:
                return None, "знаменатель inventory = 0"
            return nums["cogs"] / den * scale, None
        if spec["code"] == "asset_turnover":
            den = nums["total_assets"]
            if den == 0:
                return None, "знаменатель total_assets = 0"
            return nums["revenue"] / den * scale, None
        if spec["code"] == "debt_to_capital":
            den = nums["equity"] + nums["current_liabilities"] + nums["long_term_debt"]
            if den == 0:
                return None, "сумма капитала и долга = 0"
            return (nums["current_liabilities"] + nums["long_term_debt"]) / den * scale, None
        if spec["code"] == "debt_to_assets":
            den = nums["total_assets"]
            if den == 0:
                return None, "знаменатель total_assets = 0"
            return (nums["current_liabilities"] + nums["long_term_debt"]) / den * scale, None
        if spec["code"] == "cash_coverage":
            den = nums["current_liabilities"]
            if den == 0:
                return None, "знаменатель current_liabilities = 0"
            return nums["cf_operating"] / den * scale, None
    except (TypeError, ZeroDivisionError):
        return None, "формула неприменима"
    return None, "неизвестная формула"


def compute_ratios(frame: AnalysisFrame) -> ProcedureResult:
    available = set(frame.codes)
    items = []
    skipped_specs = []
    for spec in CATALOG:
        if not set(spec["inputs"]).issubset(available):
            skipped_specs.append({
                "code": spec["code"],
                "name": spec["name"],
                "reason": "в наборе нет всех исходных показателей",
                "needed": spec["inputs"],
                "present": [code for code in spec["inputs"] if code in available],
            })
            continue
        series = []
        for index, period in enumerate(frame.periods):
            values = {code: None if index >= len(frame.series(code)) or not _finite(frame.series(code)[index])
                      else float(frame.series(code)[index]) for code in spec["inputs"]}
            value, reason = _eval(spec, values)
            inputs = {code: values[code] for code in spec["inputs"]}
            series.append({
                "period": period,
                "value": None if value is None else round(value, 6),
                "reason": reason,
                "inputs": inputs,
            })
        finite = [row for row in series if row["value"] is not None]
        last = finite[-1] if finite else None
        prev = finite[-2] if len(finite) >= 2 else None
        abs_change = pct = None
        if last and prev and last["value"] is not None and prev["value"] is not None:
            abs_change = round(last["value"] - prev["value"], 6)
            if prev["value"] != 0:
                pct = round(100.0 * abs_change / abs(prev["value"]), 2)
        items.append({
            **{k: spec[k] for k in ("code", "name", "category", "formula", "inputs", "unit", "direction")},
            "last_value": last["value"] if last else None,
            "last_period": last["period"] if last else None,
            "previous_value": prev["value"] if prev else None,
            "abs_change": abs_change,
            "pct_change": pct,
            "series": series,
            "computed_periods": len(finite),
        })
    if not items and not skipped_specs:
        return skipped("Нет формул коэффициентов")
    return procedure(
        "ok" if items else "skipped",
        f"Рассчитано коэффициентов: {len(items)}" if items else "Исходных данных для коэффициентов недостаточно",
        {
            "method": "deterministic_ratios",
            "items": items,
            "skipped": skipped_specs,
            "note": "Коэффициент не считается, если нет исходных значений или знаменатель равен нулю. Нули вместо пропусков не подставляются.",
        },
    )


def _finite(value) -> bool:
    try:
        return value == value and value is not None and abs(float(value)) != float("inf")
    except (TypeError, ValueError):
        return False
