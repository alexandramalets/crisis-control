"""Прогноз экспоненциальным сглаживанием. При нехватке данных прогноз не выдумывается."""

import warnings as pywarnings

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error
from statsmodels.tsa.holtwinters import ExponentialSmoothing, Holt, SimpleExpSmoothing

from app.methods.frame import AnalysisFrame
from app.methods.result import procedure, skipped
from app.schemas.common import ProcedureResult

MIN_POINTS = 4
DEFAULT_HORIZON = 3


def forecast(frame: AnalysisFrame, *, horizon: int = DEFAULT_HORIZON,
             model: str = "auto") -> ProcedureResult:
    if horizon < 1:
        return skipped("Горизонт прогнозирования должен быть не меньше 1")
    series_out, skipped_codes, warnings = [], [], []
    for code in frame.codes:
        item, warn = _forecast_one(code, frame.periods, frame.series(code), horizon, model)
        warnings.extend(warn)
        if item is None:
            skipped_codes.append(code)
        else:
            series_out.append(item)

    if not series_out:
        return skipped(
            f"Недостаточно наблюдений для прогноза (нужно не менее {MIN_POINTS} значений подряд). "
            "Искусственные прогнозные значения не создаются.",
            warnings,
        )
    return procedure(
        "ok",
        f"Построен прогноз по показателям: {len(series_out)}",
        {"method_family": "exponential_smoothing", "selection": model, "horizon": horizon, "series": series_out,
         "skipped_indicators": skipped_codes},
        warnings,
    )


def _forecast_one(code: str, periods: list[str], column: np.ndarray, horizon: int, model: str):
    finite = np.isfinite(column)
    n = int(finite.sum())
    if n < MIN_POINTS:
        return None, [f"{code}: наблюдений {n} < {MIN_POINTS}, прогноз не построен"]

    # Для модели нужны последовательные числа; пропуски внутри не заполняем фиктивным прогнозом —
    # линейно интерполируем только для оценки модели и явно сообщаем об этом.
    work = pd.Series(column, dtype=float)
    interpolated = bool(work.isna().any()) and work.notna().sum() >= MIN_POINTS
    if interpolated:
        if work.isna().mean() > 0.2:
            return None, [f"{code}: слишком много пропусков для прогноза"]
        work = work.interpolate(limit_area="inside")
        work = work.bfill().ffill()
    if work.isna().any() or len(work) < MIN_POINTS:
        return None, [f"{code}: после удаления пропусков ряд слишком короткий"]

    values = work.to_numpy(dtype=float)
    notes = []
    if interpolated:
        notes.append(f"{code}: пропуски внутри ряда интерполированы только для оценки модели; "
                     "в истории возвращены исходные значения")

    chosen, errors, fitted, point = _select_model(values, horizon, model)
    if point is None or not np.isfinite(point).all():
        return None, notes + [f"{code}: модель не сошлась, прогноз не построен"]

    residuals = values - fitted
    residual_std = float(np.nanstd(residuals, ddof=1)) if len(residuals) > 2 else 0.0
    z = 1.959963984540054
    lower = point - z * residual_std
    upper = point + z * residual_std
    future = _future_periods(periods[-1], horizon)
    history = [{"period": p, "value": None if not np.isfinite(v) else _r(v)}
               for p, v in zip(periods, column, strict=True)]
    points = [
        {
            "period": future[i],
            "value": _r(point[i]),
            "lower": _r(lower[i]) if residual_std > 0 else None,
            "upper": _r(upper[i]) if residual_std > 0 else None,
        }
        for i in range(horizon)
    ]
    mape = errors.get("mape")
    return {
        "indicator": code,
        "method": {
            "ses": "simple_exponential_smoothing",
            "holt": "holt_linear",
            "seasonal": "holt_winters",
        }.get(chosen, chosen),
        "horizon": horizon,
        "history": history,
        "forecast": points,
        "errors": errors,
        "disclaimer": "Экстраполяция выбранной модели.",
        "level": None,
        "mape_applicable": mape is not None,
    }, notes


def _select_model(values: np.ndarray, horizon: int, model: str):
    holdout = min(3, max(1, len(values) // 4))
    train = values[:-holdout] if len(values) > holdout + 3 else values
    test = values[-holdout:] if len(values) > holdout + 3 else None
    candidates = ["ses"] if model == "ses" else ["holt"] if model == "holt" else ["ses", "holt"]
    if model in {"seasonal", "auto"} and len(values) >= 24:
        candidates.append("seasonal")
    best_name, best_fit, best_point, best_err = None, None, None, None
    table = {}
    with pywarnings.catch_warnings():
        pywarnings.simplefilter("ignore")
        for name in candidates:
            try:
                fitted, point = _fit(name, values, horizon)
            except Exception:
                continue
            if fitted is None or point is None:
                continue
            if test is not None and len(train) >= 4:
                try:
                    _, pred = _fit(name, train, len(test))
                    err = _errors(test, pred)
                except Exception:
                    err = _errors(values, fitted)
            else:
                err = _errors(values, fitted)
            table[name] = err
            score = err.get("mae")
            if score is None:
                continue
            if best_err is None or score < best_err:
                best_name, best_fit, best_point, best_err = name, fitted, point, score
    if best_point is None:
        fitted, point = _fit("ses", values, horizon)
        return "ses", _errors(values, fitted), fitted, point
    return best_name, table.get(best_name, {}), best_fit, best_point


def _fit(name: str, values: np.ndarray, horizon: int):
    if name == "holt":
        fit = Holt(values, initialization_method="estimated").fit(optimized=True)
    elif name == "seasonal":
        seasonal = 12 if len(values) >= 24 else 4
        fit = ExponentialSmoothing(
            values, trend="add", seasonal="add", seasonal_periods=seasonal, initialization_method="estimated",
        ).fit(optimized=True)
    else:
        try:
            fit = SimpleExpSmoothing(values, initialization_method="estimated").fit(optimized=True)
        except Exception:
            fit = SimpleExpSmoothing(values, initialization_method="heuristic").fit(optimized=True)
    fitted = np.asarray(fit.fittedvalues, dtype=float)
    point = np.asarray(fit.forecast(horizon), dtype=float)
    return fitted, point


def _errors(actual: np.ndarray, predicted: np.ndarray) -> dict:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    n = min(len(actual), len(predicted))
    if n == 0:
        return {}
    a, p = actual[-n:], predicted[-n:]
    mask = np.isfinite(a) & np.isfinite(p)
    if mask.sum() == 0:
        return {}
    a, p = a[mask], p[mask]
    mae = float(mean_absolute_error(a, p))
    rmse = float(mean_squared_error(a, p) ** 0.5)
    mape = None
    if np.all(a != 0):
        mape = float(np.mean(np.abs((a - p) / a)) * 100)
    return {"mae": round(mae, 4), "rmse": round(rmse, 4), "mape": None if mape is None else round(mape, 4)}


def _future_periods(last: str, horizon: int) -> list[str]:
    freq = "Q" if "-Q" in last.upper() else "Y" if len(last) == 4 and last.isdigit() else "M"
    try:
        period = pd.Period(last, freq=freq)
    except Exception:
        period = pd.Period(last[:7], freq="M")
    return [str(period + offset) for offset in range(1, horizon + 1)]


def _r(value: float) -> float:
    return round(float(value), 6)
