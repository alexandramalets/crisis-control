"""Многомерные выбросы Isolation Forest. Не заменяет MAD по отдельным рядам."""

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from app.methods.frame import AnalysisFrame
from app.methods.result import procedure, skipped
from app.schemas.common import ProcedureResult

MIN_ROWS = 10


def isolation_forest(frame: AnalysisFrame, *, random_state: int | None = None,
                     contamination: float | str = "auto") -> dict | None:
    complete = ~np.isnan(frame.values).any(axis=1)
    n = int(complete.sum())
    if n < MIN_ROWS or frame.n_indicators < 2:
        return None
    matrix = frame.values[complete]
    periods = [period for period, keep in zip(frame.periods, complete, strict=True) if keep]
    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)
    model = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=frame.random_state if random_state is None else random_state,
    )
    labels = model.fit_predict(scaled)
    scores = model.decision_function(scaled)
    outliers = []
    med = np.median(scaled, axis=0)
    for i, period in enumerate(periods):
        if labels[i] != -1:
            continue
        contrib = np.abs(scaled[i] - med)
        order = np.argsort(contrib)[::-1]
        outliers.append({
            "period": period,
            "score": round(float(scores[i]), 6),
            "contributors": [
                {"indicator": frame.codes[j], "share": round(float(contrib[j] / (contrib.sum() or 1)), 4)}
                for j in order[: min(5, len(order))]
            ],
            "method": "isolation_forest",
        })
    return {
        "method": "isolation_forest",
        "n_observations": n,
        "outliers": outliers,
        "note": "Вклад — доля отклонения от медианы масштабированных признаков.",
    }


def maybe_multivariate(frame: AnalysisFrame) -> ProcedureResult:
    payload = isolation_forest(frame)
    if payload is None:
        return skipped(
            f"Isolation Forest не применяется: нужно ≥ {MIN_ROWS} полных периодов и ≥ 2 показателей"
        )
    return procedure(
        "ok",
        f"Многомерных выбросов: {len(payload['outliers'])}",
        payload,
    )
