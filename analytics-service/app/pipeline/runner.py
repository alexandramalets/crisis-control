"""Конвейер процедур. Каждая ошибка не отменяет остальные."""

import logging

from app.methods.anomalies import detect_anomalies
from app.methods.assessment import assess
from app.methods.clustering import cluster
from app.methods.correlation import correlate
from app.methods.forecasting import forecast
from app.methods.frame import AnalysisFrame, quality_report
from app.methods.multivariate import isolation_forest
from app.methods.ratios import compute_ratios
from app.methods.trends import detect_trends
from app.schemas.common import ProcedureResult
from app.schemas.requests import AnalyzeRequest

logger = logging.getLogger(__name__)

DEFAULT_ORDER = (
    "validate", "ratios", "anomalies", "trends", "correlation", "clustering", "forecast", "assessment",
)


def run_pipeline(frame: AnalysisFrame, request: AnalyzeRequest) -> dict[str, ProcedureResult]:
    selected = tuple(request.procedures) if request.procedures else DEFAULT_ORDER
    out: dict[str, ProcedureResult] = {}
    for name in selected:
        try:
            out[name] = _run_one(name, frame, request)
            logger.info("procedure=%s status=%s request_id=%s", name, out[name].status, frame.request_id)
        except Exception:
            logger.exception("procedure=%s failed request_id=%s", name, frame.request_id)
            out[name] = ProcedureResult(status="error", message="Внутренняя ошибка процедуры", result=None)
    return out


def _run_one(name: str, frame: AnalysisFrame, request: AnalyzeRequest) -> ProcedureResult:
    if name == "validate":
        report = quality_report(frame)
        status = "ok" if report["sufficient"] else "skipped"
        return ProcedureResult(status=status, message=report["message"] or "Проверка данных выполнена",
                               result=report)
    if name == "anomalies":
        params = request.anomalies or {}
        method = params.get("method", "robust_z")
        univariate = detect_anomalies(
            frame, method="zscore" if method == "zscore" else "robust_z",
            threshold=params.get("threshold", 3.0),
            min_observations=params.get("min_observations", 6),
        )
        multi = isolation_forest(frame)
        if univariate.result is not None and multi:
            univariate.result["multivariate"] = multi
            extra = len(multi.get("outliers") or [])
            univariate.message = f"{univariate.message}; многомерных выбросов: {extra}"
        return univariate
    if name == "trends":
        return detect_trends(frame)
    if name == "ratios":
        return compute_ratios(frame)
    if name == "correlation":
        params = request.correlation or {}
        return correlate(
            frame,
            min_observations=params.get("min_observations", 4),
            method=params.get("method", "pearson"),
        )
    if name == "clustering":
        params = request.clustering or {}
        return cluster(frame, k=params.get("k", "auto"), k_min=params.get("k_min", 2),
                       k_max=params.get("k_max", 6), random_state=frame.random_state)
    if name == "forecast":
        params = request.forecast or {}
        return forecast(frame, horizon=params.get("horizon", 3), model=params.get("model", "auto"))
    if name == "assessment":
        return assess(frame)
    return ProcedureResult(status="error", message=f"Неизвестная процедура: {name}")
