"""ORM-модели. Импорт модуля регистрирует все таблицы в Base.metadata (нужно Alembic)."""

from app.models.analysis import AnalysisParameter, AnalysisProcedure, AnalysisRun, AnalysisRunIndicator
from app.models.audit import AuditLog
from app.models.dataset import Dataset, DatasetFile, DatasetIssue, IndicatorValue
from app.models.governance import (
    AnalysisAlert, AnalysisFinding, CrisisMeasure, MeasureEvent, Recommendation, RatioResult, WhatIfScenario,
)
from app.models.organization import Category, Organization, OrganizationAccess
from app.models.reference import Indicator, IndicatorGroup, Period, Unit
from app.models.report import Report
from app.models.results import (
    AnomalyBaseline, AnomalyResult, Assessment, AssessmentComponent, Cluster, ClusterCentroid,
    ClusterMember, CorrelationResult, ForecastPoint, ForecastSeries, PreprocessingAction,
    ProcedureMetric, TrendResult,
)
from app.models.target import IndicatorTarget, IndicatorThreshold
from app.models.user import RefreshToken, Role, User, UserSession

__all__ = [
    "AnalysisAlert", "AnalysisFinding", "AnalysisParameter", "AnalysisProcedure", "AnalysisRun",
    "AnalysisRunIndicator", "AnomalyBaseline", "CrisisMeasure", "MeasureEvent", "RatioResult",
    "Recommendation", "WhatIfScenario",
    "AnomalyResult", "Assessment", "AssessmentComponent", "AuditLog", "Category", "Cluster",
    "ClusterCentroid", "ClusterMember", "CorrelationResult", "Dataset", "DatasetFile", "DatasetIssue",
    "ForecastPoint", "ForecastSeries", "Indicator", "IndicatorGroup", "IndicatorTarget",
    "IndicatorThreshold", "IndicatorValue", "Organization", "OrganizationAccess", "Period", "PreprocessingAction",
    "ProcedureMetric", "RefreshToken", "Report", "Role", "TrendResult", "Unit", "User", "UserSession",
]
