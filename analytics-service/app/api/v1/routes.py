import logging
from importlib.metadata import version

from fastapi import APIRouter, Depends

from app import __version__
from app.core.config import Settings, get_settings
from app.core.security import require_service_key
from app.methods.anomalies import detect_anomalies
from app.methods.assessment import assess
from app.methods.clustering import cluster
from app.methods.correlation import correlate
from app.methods.forecasting import forecast
from app.methods.frame import quality_report
from app.methods.ratios import compute_ratios
from app.methods.trends import detect_trends
from app.pipeline.runner import run_pipeline
from app.schemas.common import ProcedureResult
from app.schemas.requests import (
    AnalyzeRequest, AnomalyRequest, AssessmentRequest, ClusteringRequest, CorrelationRequest,
    ForecastRequest, require_frame,
)

LIBRARIES = ("pandas", "numpy", "scipy", "scikit-learn", "statsmodels")
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics/v1")
protected = [Depends(require_service_key)]


@router.get("/health", tags=["Состояние"], summary="Проверка работоспособности")
def health():
    return {
        "status": "ok",
        "service": "analytics-service",
        "version": __version__,
        "libraries": {name: version(name) for name in LIBRARIES},
    }


@router.get("/capabilities", tags=["Методы"], summary="Доступные аналитические процедуры",
            dependencies=protected)
def capabilities(settings: Settings = Depends(get_settings)):
    return {
        "version": __version__,
        "default_random_state": settings.default_random_state,
        "notes": [
            "Корреляция — совместное движение рядов.",
            "Номер группы — не категория риска.",
        ],
        "procedures": [
            {
                "type": "validate", "path": "/analytics/v1/validate",
                "description": "Проверка полноты, пропусков и пригодности рядов",
            },
            {
                "type": "anomalies", "path": "/analytics/v1/anomalies", "methods": ["robust_z", "zscore"],
                "defaults": {"method": "robust_z", "threshold": 3.0, "min_observations": 6},
                "description": "Выбросы по медиане и MAD; при MAD=0 — классическая z-оценка",
            },
            {
                "type": "trends", "path": "/analytics/v1/trends",
                "description": "Theil–Sen и Kendall: направление, скорость, значимость при n≥6",
            },
            {
                "type": "ratios", "path": "/analytics/v1/ratios",
                "description": "Производные коэффициенты только при наличии исходных показателей",
            },
            {
                "type": "correlation", "path": "/analytics/v1/correlation", "methods": ["pearson", "spearman"],
                "defaults": {"min_observations": 4},
                "description": "Корреляции Пирсона или Спирмена; p-value при достаточном n",
            },
            {
                "type": "clustering", "path": "/analytics/v1/clustering", "methods": ["kmeans"],
                "defaults": {"k": "auto", "k_min": 2, "k_max": 6, "scaler": "standard"},
                "description": "k-средних с StandardScaler; k по силуэту, если k=auto",
            },
            {
                "type": "forecast", "path": "/analytics/v1/forecast",
                "methods": ["simple_exponential_smoothing"],
                "defaults": {"horizon": 3, "min_observations": 4},
                "description": "Экспоненциальное сглаживание; без искусственных значений при нехватке данных",
            },
            {
                "type": "assessment", "path": "/analytics/v1/assessment",
                "defaults": {"scale": [0, 100]},
                "description": "Сводная оценка 0–100 с учётом направления влияния и весов",
            },
            {
                "type": "analyze", "path": "/analytics/v1/analyze",
                "description": "Конвейер выбранных процедур",
            },
        ],
    }


@router.post("/validate", tags=["Проверка"], summary="Проверка аналитических данных",
             response_model=ProcedureResult, dependencies=protected)
def validate_data(payload: AnalyzeRequest):
    frame = require_frame(payload)
    report = quality_report(frame)
    status = "ok" if report["sufficient"] else "skipped"
    return ProcedureResult(status=status, message=report["message"] or "Проверка данных выполнена", result=report)


@router.post("/anomalies", tags=["Аномалии"], summary="Обнаружение аномалий (медиана и MAD)",
             response_model=ProcedureResult, dependencies=protected)
def anomalies_endpoint(payload: AnomalyRequest):
    frame = require_frame(payload)
    return detect_anomalies(frame, method=payload.method, threshold=payload.threshold,
                            min_observations=payload.min_observations)


@router.post("/trends", tags=["Тенденции"], summary="Анализ динамики",
             response_model=ProcedureResult, dependencies=protected)
def trends_endpoint(payload: AnalyzeRequest):
    return detect_trends(require_frame(payload))


@router.post("/ratios", tags=["Коэффициенты"], summary="Финансово-экономические коэффициенты",
             response_model=ProcedureResult, dependencies=protected)
def ratios_endpoint(payload: AnalyzeRequest):
    return compute_ratios(require_frame(payload))


@router.post("/correlation", tags=["Корреляции"], summary="Корреляционная матрица",
             response_model=ProcedureResult, dependencies=protected)
def correlation_endpoint(payload: CorrelationRequest):
    frame = require_frame(payload)
    return correlate(frame, min_observations=payload.min_observations, method=payload.method)


@router.post("/clustering", tags=["Кластеризация"], summary="Кластеризация k-средних",
             response_model=ProcedureResult, dependencies=protected)
def clustering_endpoint(payload: ClusteringRequest):
    frame = require_frame(payload)
    return cluster(frame, k=payload.k, k_min=payload.k_min, k_max=payload.k_max,
                   random_state=payload.random_state)


@router.post("/forecast", tags=["Прогноз"], summary="Экспоненциальное сглаживание",
             response_model=ProcedureResult, dependencies=protected)
def forecast_endpoint(payload: ForecastRequest):
    frame = require_frame(payload)
    return forecast(frame, horizon=payload.horizon, model=payload.model)


@router.post("/assessment", tags=["Оценка"], summary="Комплексная оценка состояния 0–100",
             response_model=ProcedureResult, dependencies=protected)
def assessment_endpoint(payload: AssessmentRequest):
    frame = require_frame(payload)
    return assess(frame)


@router.post("/analyze", tags=["Конвейер"], summary="Полный или выбранный набор процедур",
             dependencies=protected)
def analyze_endpoint(payload: AnalyzeRequest):
    frame = require_frame(payload)
    procedures = run_pipeline(frame, payload)
    return {
        "service_version": __version__,
        "request_id": payload.request_id,
        "random_state": payload.random_state,
        "procedures": {name: result.model_dump() for name, result in procedures.items()},
    }
