"""Анализ динамики показателя. Не подменяет аномалии MAD и не ставит диагноз кризиса."""

import numpy as np
from scipy import stats

from app.methods.frame import AnalysisFrame
from app.methods.result import procedure, skipped
from app.schemas.common import ProcedureResult

MIN_POINTS = 3
MIN_SIGNIFICANCE = 6


def detect_trends(frame: AnalysisFrame) -> ProcedureResult:
    if frame.n_periods < MIN_POINTS:
        return skipped(f"Для анализа тенденции нужно не менее {MIN_POINTS} периодов")
    items, warnings = [], []
    for code in frame.codes:
        meta = frame.meta[code]
        item, warn = _one(code, frame.periods, frame.series(code), meta.direction)
        warnings.extend(warn)
        if item is not None:
            items.append(item)
    if not items:
        return skipped("Ни по одному показателю тенденция не рассчитана", warnings)
    return procedure(
        "ok",
        f"Тенденции рассчитаны по {len(items)} показателям",
        {
            "method": "theil_sen_kendall",
            "items": items,
            "note": "Направление улучшения берётся из справочника показателя. Ухудшение — не синоним кризиса.",
        },
        warnings,
    )


def _one(code: str, periods: list[str], column: np.ndarray, direction: str):
    mask = np.isfinite(column)
    n = int(mask.sum())
    warnings = []
    if n < MIN_POINTS:
        return None, [f"{code}: наблюдений {n} < {MIN_POINTS}"]
    y = column[mask]
    x = np.arange(n, dtype=float)
    finite_idx = np.where(mask)[0]
    last = float(y[-1])
    prev = float(y[-2]) if n >= 2 else None
    first = float(y[0])
    abs_change = last - prev if prev is not None else None
    growth = None if prev in (None, 0) else last / prev
    pct = None if prev in (None, 0) else 100.0 * (last - prev) / abs(prev)
    avg_change = (last - first) / (n - 1) if n > 1 else 0.0
    slope, intercept, lo, hi = stats.theilslopes(y, x)
    tau = p_value = None
    if n >= MIN_SIGNIFICANCE:
        tau, p_value = stats.kendalltau(x, y)
        if not np.isfinite(p_value):
            p_value = None
        if not np.isfinite(tau):
            tau = None
    else:
        warnings.append(f"{code}: значимость тренда не считается (нужно ≥ {MIN_SIGNIFICANCE} точек)")

    consecutive = _consecutive_worsening(y, direction)
    raw_direction = "up" if last > first else "down" if last < first else "flat"
    favorable = _favorable(raw_direction, direction)
    if direction == "neutral":
        trend_label = "без однозначной оценки знака"
    elif favorable is True:
        trend_label = "улучшение относительно направления показателя"
    elif favorable is False:
        trend_label = "ухудшение относительно направления показателя"
    else:
        trend_label = "без выраженного направления"
    speed = abs(float(slope))
    significant = bool(
        p_value is not None and float(p_value) < 0.05 and abs(float(tau or 0)) >= 0.3
    )
    return {
        "indicator": code,
        "impact_direction": direction,
        "n_observations": n,
        "last_period": periods[int(finite_idx[-1])],
        "last_value": _r(last),
        "previous_value": None if prev is None else _r(prev),
        "first_value": _r(first),
        "abs_change": None if abs_change is None else _r(abs_change),
        "growth_rate": None if growth is None else _r(growth),
        "pct_change": None if pct is None else _r(pct, 2),
        "average_change": _r(avg_change),
        "slope": _r(float(slope)),
        "intercept": _r(float(intercept)),
        "slope_low": _r(float(lo)),
        "slope_high": _r(float(hi)),
        "kendall_tau": None if tau is None else _r(float(tau)),
        "p_value": None if p_value is None else _r(float(p_value), 4),
        "significant": significant,
        "raw_direction": raw_direction,
        "favorable": favorable,
        "label": trend_label,
        "consecutive_worsening": consecutive,
        "speed": _r(speed),
        "trend_line": [
            {"period": periods[int(finite_idx[i])], "value": _r(float(intercept + slope * i))}
            for i in range(n)
        ],
    }, warnings


def _consecutive_worsening(y: np.ndarray, direction: str) -> int:
    if direction not in {"higher_better", "lower_better"} or len(y) < 2:
        return 0
    count = 0
    for i in range(len(y) - 1, 0, -1):
        worse = (y[i] < y[i - 1]) if direction == "higher_better" else (y[i] > y[i - 1])
        if worse:
            count += 1
        else:
            break
    return count


def _favorable(raw: str, direction: str):
    if raw == "flat" or direction == "neutral":
        return None
    if direction == "higher_better":
        return raw == "up"
    if direction == "lower_better":
        return raw == "down"
    return None


def _r(value: float, digits: int = 6) -> float:
    return round(float(value), digits)
