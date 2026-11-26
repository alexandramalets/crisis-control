"""Корреляционный анализ Пирсона. Корреляция не означает причинность."""

import warnings

import numpy as np
from scipy import stats

from app.methods.frame import AnalysisFrame
from app.methods.result import procedure, skipped
from app.schemas.common import ProcedureResult

MIN_PAIR = 4
NOTE = (
    "Коэффициент корреляции описывает статистическую связь, а не причинно-следственную. "
    "Интерпретировать его как причину нельзя."
)


def correlate(frame: AnalysisFrame, *, min_observations: int = MIN_PAIR,
              method: str = "pearson") -> ProcedureResult:
    if frame.n_indicators < 2:
        return skipped("Для корреляции нужно не менее двух показателей")
    if frame.n_periods < min_observations:
        return skipped(
            f"Недостаточно наблюдений для корреляции (нужно не менее {min_observations} периодов)"
        )

    pairs, warnings = [], []
    n = frame.n_indicators
    matrix = [[None] * n for _ in range(n)]
    for i, a in enumerate(frame.codes):
        matrix[i][i] = 1.0
        for j in range(i + 1, n):
            b = frame.codes[j]
            coeff, p_value, count, note = _pair(
                frame.series(a), frame.series(b), min_observations, method,
            )
            if note:
                warnings.append(f"{a}–{b}: {note}")
            item = {
                "indicator_a": a, "indicator_b": b, "coefficient": coeff, "p_value": p_value,
                "n_observations": count, "note": note,
            }
            pairs.append(item)
            matrix[i][j] = matrix[j][i] = coeff

    defined = sum(1 for item in pairs if item["coefficient"] is not None)
    if defined == 0:
        return skipped("Ни для одной пары показателей коэффициент не определён", warnings)
    return procedure(
        "ok",
        f"Рассчитано пар: {defined} из {len(pairs)}",
        {
            "method": method if method in {"pearson", "spearman"} else "pearson",
            "min_observations": min_observations,
            "indicators": frame.codes,
            "pairs": pairs,
            "matrix": matrix,
            "interpretation": NOTE,
        },
        warnings,
    )


def _pair(x: np.ndarray, y: np.ndarray, min_observations: int, method: str):
    mask = np.isfinite(x) & np.isfinite(y)
    count = int(mask.sum())
    if count < min_observations:
        return None, None, count, f"недостаточно совместных наблюдений ({count} < {min_observations})"
    xs, ys = x[mask], y[mask]
    if np.std(xs) == 0 or np.std(ys) == 0:
        return None, None, count, "постоянный ряд: коэффициент не определён"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if method == "spearman":
            coefficient, p_value = stats.spearmanr(xs, ys)
        else:
            coefficient, p_value = stats.pearsonr(xs, ys)
    if not np.isfinite(coefficient):
        return None, None, count, "коэффициент не определён"
    p = None if not np.isfinite(p_value) else round(float(p_value), 6)
    note = None
    if count < 8:
        note = "p-значение при малой выборке (< 8 точек) интерпретировать осторожно"
    return round(float(coefficient), 6), p, count, note
