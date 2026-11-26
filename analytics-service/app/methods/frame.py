"""Проверка аналитических данных и построение матрицы наблюдений."""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.core.errors import ServiceError
from app.schemas.common import DataPayload, ImpactDirection


@dataclass
class IndicatorMeta:
    code: str
    direction: ImpactDirection
    weight: float | None
    lower_bound: float | None
    upper_bound: float | None


@dataclass
class AnalysisFrame:
    periods: list[str]
    codes: list[str]
    values: np.ndarray  # (n_periods, n_indicators), float, NaN = пропуск
    meta: dict[str, IndicatorMeta]
    random_state: int
    request_id: str | None

    @property
    def n_periods(self) -> int:
        return len(self.periods)

    @property
    def n_indicators(self) -> int:
        return len(self.codes)

    def series(self, code: str) -> np.ndarray:
        return self.values[:, self.codes.index(code)]

    def as_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self.values, index=self.periods, columns=self.codes)


def build_frame(payload: DataPayload) -> AnalysisFrame:
    errors = payload.length_errors()
    if errors:
        raise ServiceError("Набор данных не прошёл проверку", details={"errors": errors}, code="invalid_data")
    codes = [item.code for item in payload.indicators]
    matrix = np.column_stack([
        np.array([np.nan if v is None else float(v) for v in item.values], dtype=float)
        for item in payload.indicators
    ])
    if matrix.size and not np.isfinite(matrix[~np.isnan(matrix)]).all():
        raise ServiceError("Значения содержат бесконечность", code="invalid_data")
    meta = {
        item.code: IndicatorMeta(item.code, item.impact_direction, item.weight, item.lower_bound, item.upper_bound)
        for item in payload.indicators
    }
    return AnalysisFrame(list(payload.periods), codes, matrix, meta, payload.random_state, payload.request_id)


def quality_report(frame: AnalysisFrame) -> dict:
    rows = []
    for index, code in enumerate(frame.codes):
        column = frame.values[:, index]
        finite = column[~np.isnan(column)]
        missing = int(np.isnan(column).sum())
        constant = bool(finite.size >= 2 and np.nanstd(column) == 0)
        rows.append({
            "code": code,
            "observations": int(finite.size),
            "missing": missing,
            "missing_share": round(missing / frame.n_periods, 4),
            "constant": constant,
            "min": _num(finite.min()) if finite.size else None,
            "max": _num(finite.max()) if finite.size else None,
            "usable_for_time_analysis": int(finite.size) >= 3 and not constant,
        })
    usable = [row for row in rows if row["usable_for_time_analysis"]]
    return {
        "n_periods": frame.n_periods,
        "n_indicators": frame.n_indicators,
        "indicators": rows,
        "sufficient": len(usable) >= 1 and frame.n_periods >= 3,
        "message": None if len(usable) >= 1 and frame.n_periods >= 3 else "Недостаточно данных",
    }


def _num(value) -> float:
    return float(value)
