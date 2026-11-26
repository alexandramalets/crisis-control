"""Обнаружение аномалий: устойчивая z-оценка по медиане и MAD (формула 3)."""

import numpy as np
from scipy import stats

from app.methods.frame import AnalysisFrame
from app.methods.result import failed, procedure, skipped
from app.schemas.common import ProcedureResult

DEFAULT_THRESHOLD = 3.0
MIN_OBSERVATIONS = 6
# 0.6745 ≈ Φ^{-1}(0.75): при нормальном распределении robust_z совпадает с классической z-оценкой
CONSISTENCY = 0.6744897501960817


def detect_anomalies(frame: AnalysisFrame, *, method: str = "robust_z",
                     threshold: float = DEFAULT_THRESHOLD,
                     min_observations: int = MIN_OBSERVATIONS) -> ProcedureResult:
    if method not in {"robust_z", "zscore"}:
        return failed(f"Неизвестный метод обнаружения аномалий: {method}")
    if threshold <= 0:
        return failed("Порог должен быть положительным")

    anomalies, baselines, warnings = [], [], []
    skipped_codes = []
    for code in frame.codes:
        column = frame.series(code)
        found, baseline, warn = _scan_indicator(
            frame.periods, code, column, method, threshold, min_observations,
        )
        warnings.extend(warn)
        if baseline is None:
            skipped_codes.append(code)
            continue
        baselines.append(baseline)
        anomalies.extend(found)

    if not baselines:
        return skipped(
            f"Недостаточно наблюдений для обнаружения аномалий "
            f"(нужно не менее {min_observations} значений у показателя)",
            warnings,
        )
    return procedure(
        "ok",
        f"Обнаружено аномалий: {len(anomalies)}" if anomalies else "Аномалий не обнаружено",
        {
            "method": method,
            "threshold": threshold,
            "min_observations": min_observations,
            "anomalies": anomalies,
            "baselines": baselines,
            "skipped_indicators": skipped_codes,
        },
        warnings,
    )


def _scan_indicator(periods, code, column, method, threshold, min_observations):
    finite_mask = np.isfinite(column)
    n = int(finite_mask.sum())
    if n < min_observations:
        return [], None, [f"{code}: пропущен (наблюдений {n} < {min_observations})"]

    values = column[finite_mask]
    used_method = method
    warnings = []
    center = float(np.median(values)) if method == "robust_z" else float(np.mean(values))
    scale = float(stats.median_abs_deviation(values, scale="normal")) if method == "robust_z" else float(np.std(values, ddof=1))

    if method == "robust_z" and (scale == 0 or not np.isfinite(scale)):
        # MAD = 0: все отклонения от медианы нулевые — пробуем классическую z-оценку
        used_method = "zscore"
        center = float(np.mean(values))
        scale = float(np.std(values, ddof=1))
        warnings.append(f"{code}: MAD равен нулю, использована классическая z-оценка")

    if scale == 0 or not np.isfinite(scale):
        return [], {
            "indicator": code, "center": center, "lower_bound": center, "upper_bound": center,
            "scale": 0.0, "method": used_method,
        }, warnings + [f"{code}: ряд постоянный, аномалии не определяются"]

    lower = center - threshold * scale
    upper = center + threshold * scale
    baseline = {
        "indicator": code, "center": _r(center), "lower_bound": _r(lower), "upper_bound": _r(upper),
        "scale": _r(scale), "method": used_method,
    }
    found = []
    for period, value in zip(periods, column, strict=True):
        if not np.isfinite(value):
            continue
        score = (float(value) - center) / scale
        if abs(score) <= threshold:
            continue
        found.append({
            "indicator": code,
            "period": period,
            "value": _r(value),
            "baseline": _r(center),
            "deviation": _r(float(value) - center),
            "score": _r(score),
            "direction": "above" if value > center else "below",
            "method": used_method,
        })
    return found, baseline, warnings


def _r(value: float, digits: int = 6) -> float:
    return round(float(value), digits)
