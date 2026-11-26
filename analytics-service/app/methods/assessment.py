"""Интерпретируемая оценка состояния 0–100. Высокий балл — устойчивее, низкий — больше признаков риска."""

import numpy as np

from app.methods.frame import AnalysisFrame, IndicatorMeta
from app.methods.result import procedure, skipped
from app.schemas.common import ProcedureResult

MIN_PERIODS = 3
DIRECTION_LABEL = {
    "higher_better": "чем выше значение, тем устойчивее состояние",
    "lower_better": "чем ниже значение, тем устойчивее состояние",
    "neutral": "близость к типичному уровню ряда",
}


def assess(frame: AnalysisFrame) -> ProcedureResult:
    if frame.n_periods < MIN_PERIODS:
        return skipped("Недостаточно данных")

    components, skipped_codes = [], []
    for code in frame.codes:
        item, reason = _component(code, frame.series(code), frame.meta[code])
        if item is None:
            skipped_codes.append({"code": code, "reason": reason})
        else:
            components.append(item)

    if not components:
        return procedure(
            "skipped",
            "Недостаточно данных",
            {
                "status": "insufficient_data",
                "status_label": "Недостаточно данных",
                "score": None,
                "components": [],
                "skipped_indicators": skipped_codes,
            },
        )

    raw_weights = np.array([c["weight"] for c in components], dtype=float)
    if raw_weights.sum() <= 0:
        raw_weights = np.ones(len(components))
    weights = raw_weights / raw_weights.sum()
    for component, weight in zip(components, weights, strict=True):
        component["weight"] = _r(float(weight))
        component["contribution"] = _r(float(weight) * component["normalized_score"] * 100)

    score = float(np.dot(weights, [c["normalized_score"] for c in components]) * 100)
    history = [c for c in components if c.get("range_source") == "series_minmax"]
    compliance = [c for c in components if c.get("range_source") == "thresholds"]
    history_score = _weighted(history)
    compliance_score = _weighted(compliance)
    completeness = round(len(components) / max(len(frame.codes), 1), 4)
    composite = None
    composite_note = "Исторический балл — по диапазону собственного ряда."
    if history_score is not None and compliance_score is not None and len(compliance) >= 3:
        composite = round(0.5 * history_score + 0.5 * compliance_score, 2)
        composite_note = "Сводный балл: 0,5·история + 0,5·соответствие порогам."
    display = compliance_score if compliance_score is not None else history_score
    label = "Рассчитано"
    if display is None:
        label = "Недостаточно данных для оценки"
    return procedure(
        "ok",
        f"Оценка динамики {history_score:.1f} из 100" if history_score is not None else label,
        {
            "status": "ok" if display is not None else "insufficient_data",
            "status_label": label,
            "score": None if display is None else _r(display, 2),
            "history_score": history_score,
            "compliance_score": compliance_score,
            "composite_score": composite,
            "completeness": completeness,
            "scale": {"min": 0, "max": 100, "high_means": "ближе к благоприятной стороне выбранной шкалы"},
            "formula": "q_j по направлению влияния; история — min–max ряда; соответствие — пороги организации",
            "components": components,
            "skipped_indicators": skipped_codes,
            "n_indicators_used": len(components),
            "note": composite_note,
        },
    )


def _weighted(items: list[dict]) -> float | None:
    if not items:
        return None
    raw = np.array([c["weight"] for c in items], dtype=float)
    if raw.sum() <= 0:
        raw = np.ones(len(items))
    weights = raw / raw.sum()
    return _r(float(np.dot(weights, [c["normalized_score"] for c in items]) * 100), 2)


def _component(code: str, column: np.ndarray, meta: IndicatorMeta):
    finite = column[np.isfinite(column)]
    if finite.size < 2:
        return None, "слишком мало значений для нормализации"
    last_idx = np.where(np.isfinite(column))[0][-1]
    last = float(column[last_idx])

    low, high, source = _bounds(finite, meta)
    if high <= low:
        return None, "нет вариации и не задан диапазон порогов"

    if meta.direction == "higher_better":
        q = (last - low) / (high - low)
        meaning = "выше последнего значения относительно диапазона — лучше"
    elif meta.direction == "lower_better":
        q = (high - last) / (high - low)
        meaning = "ниже последнего значения относительно диапазона — лучше"
    else:
        center = float(np.median(finite))
        span = max(high - low, 1e-12)
        q = 1.0 - min(abs(last - center) / (span / 2), 1.0)
        meaning = "ближе к медиане ряда — нейтральнее"

    q = float(np.clip(q, 0.0, 1.0))
    weight = 1.0 if meta.weight is None else float(meta.weight)
    explanation = (
        f"{code}: последнее значение {_r(last)} при диапазоне {_r(low)}–{_r(high)} "
        f"({DIRECTION_LABEL[meta.direction]}). Нормализованная оценка q={_r(q, 4)}. {meaning}."
    )
    return {
        "indicator": code,
        "impact_direction": meta.direction,
        "last_value": _r(last),
        "range_low": _r(low),
        "range_high": _r(high),
        "range_source": source,
        "normalized_score": _r(q, 4),
        "weight": weight,
        "explanation": explanation,
    }, None


def _bounds(finite: np.ndarray, meta: IndicatorMeta) -> tuple[float, float, str]:
    if meta.lower_bound is not None and meta.upper_bound is not None and meta.upper_bound > meta.lower_bound:
        return float(meta.lower_bound), float(meta.upper_bound), "thresholds"
    return float(np.min(finite)), float(np.max(finite)), "series_minmax"


def _r(value: float, digits: int = 6) -> float:
    return round(float(value), digits)
