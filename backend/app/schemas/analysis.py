from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AnalysisStatus, ProcedureStatus, ProcedureType
from app.schemas.common import ORMModel


class AnalysisSummary(BaseModel):
    id: int
    dataset_id: int
    dataset_name: str
    organization_id: int
    organization_name: str | None = None
    created_by: int
    parent_run_id: int | None
    status: AnalysisStatus
    period_from: date
    period_to: date
    created_at: datetime
    finished_at: datetime | None


class AnalysisIndicatorRead(BaseModel):
    indicator_id: int
    code: str
    name: str
    weight: Decimal


class AnalysisParameterRead(ORMModel):
    name: str
    position: int
    numeric_value: Decimal | None
    text_value: str | None
    boolean_value: bool | None


class AnalysisProcedureRead(ORMModel):
    id: int
    procedure_type: ProcedureType
    method: str
    status: ProcedureStatus
    message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    parameters: list[AnalysisParameterRead]


class AnalysisDetail(AnalysisSummary):
    random_state: int
    analytics_service_version: str | None
    error_message: str | None
    started_at: datetime | None
    indicators: list[AnalysisIndicatorRead]
    procedures: list[AnalysisProcedureRead]


ProcedureName = Literal[
    "validate", "ratios", "anomalies", "trends", "correlation", "clustering", "forecast", "assessment",
]


class AnalysisIndicatorIn(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=50)
    indicator_id: int | None = None
    weight: Decimal | None = Field(None, ge=0, le=1)

    @model_validator(mode="after")
    def has_key(self):
        if self.code is None and self.indicator_id is None:
            raise ValueError("Укажите code или indicator_id")
        return self


class AnomalyParams(BaseModel):
    method: Literal["robust_z", "zscore"] = "robust_z"
    threshold: float = Field(3.0, gt=0, le=10)
    min_observations: int = Field(6, ge=3, le=24)


class CorrelationParams(BaseModel):
    method: Literal["pearson", "spearman"] = "pearson"
    min_observations: int = Field(4, ge=3, le=24)


class ClusteringParams(BaseModel):
    k: int | Literal["auto"] = "auto"
    k_min: int = Field(2, ge=2, le=10)
    k_max: int = Field(6, ge=2, le=15)

    @model_validator(mode="after")
    def k_range(self):
        if self.k_max < self.k_min:
            raise ValueError("k_max не может быть меньше k_min")
        if isinstance(self.k, int) and self.k < 1:
            raise ValueError("k должно быть положительным или auto")
        return self


class ForecastParams(BaseModel):
    horizon: int = Field(3, ge=1, le=24)
    model: Literal["auto", "ses", "holt", "seasonal"] = "auto"


class AnalysisCreate(BaseModel):
    dataset_id: int
    period_from: date | None = None
    period_to: date | None = None
    random_state: int = Field(42, ge=0)
    parent_run_id: int | None = None
    indicators: list[AnalysisIndicatorIn] | None = None
    procedures: list[ProcedureName] | None = None
    anomalies: AnomalyParams | None = None
    correlation: CorrelationParams | None = None
    clustering: ClusteringParams | None = None
    forecast: ForecastParams | None = None

    @model_validator(mode="after")
    def period_order(self):
        if self.period_from and self.period_to and self.period_from > self.period_to:
            raise ValueError("Начало периода не может быть позже конца")
        return self


class AnalysisAccepted(BaseModel):
    id: int
    status: AnalysisStatus
    error_message: str | None = None


class AnomalyItem(BaseModel):
    indicator: str
    indicator_name: str
    period_start: date
    value: Decimal | None
    baseline: Decimal
    deviation: Decimal | None
    score: float
    direction: Literal["above", "below"]
    lower_bound: Decimal
    upper_bound: Decimal


class AnomalyResults(BaseModel):
    status: ProcedureStatus
    message: str | None
    method: str | None = None
    items: list[AnomalyItem]
    baselines: list[dict]


class CorrelationItem(BaseModel):
    indicator_a: str
    indicator_b: str
    coefficient: float | None
    p_value: float | None
    n_observations: int


class CorrelationResults(BaseModel):
    status: ProcedureStatus
    message: str | None
    interpretation: str = (
        "Коэффициент описывает статистическую связь, а не причинность."
    )
    pairs: list[CorrelationItem]


class ClusterProfile(BaseModel):
    cluster: int
    label: str | None
    size: int
    centroid: dict[str, Decimal]


class ClusterMemberRead(BaseModel):
    period_start: date
    cluster: int
    pc1: float | None
    pc2: float | None


class ClusterResults(BaseModel):
    status: ProcedureStatus
    message: str | None
    algorithm: str = "kmeans"
    metrics: dict[str, float]
    clusters: list[ClusterProfile]
    members: list[ClusterMemberRead]
    interpretation: str = "Подпись отражает сравнение центров групп с учётом направления влияния показателей."


class ForecastPointRead(BaseModel):
    period_start: date
    value: Decimal
    lower_bound: Decimal | None
    upper_bound: Decimal | None


class ForecastSeriesRead(BaseModel):
    indicator: str
    method: str
    points: list[ForecastPointRead]


class ForecastResults(BaseModel):
    status: ProcedureStatus
    message: str | None
    series: list[ForecastSeriesRead]


class AssessmentComponentRead(BaseModel):
    indicator: str
    indicator_name: str
    weight: Decimal
    normalized_score: Decimal
    contribution: Decimal | None = None
    explanation: str | None = None


class AssessmentResults(BaseModel):
    status: ProcedureStatus
    message: str | None
    status_label: str | None = None
    score: Decimal | None
    history_score: Decimal | None = None
    compliance_score: Decimal | None = None
    completeness: Decimal | None = None
    interpretation: str | None = None
    methodology: str | None = None
    disclaimer: str | None = None
    components: list[AssessmentComponentRead]


class TrendItemRead(BaseModel):
    indicator: str
    slope: float | None = None
    intercept: float | None = None
    kendall_tau: float | None = None
    p_value: float | None = None
    abs_change: float | None = None
    pct_change: float | None = None
    consecutive_worsening: int | None = None
    label: str | None = None
    significant: bool | None = None


class TrendResults(BaseModel):
    status: ProcedureStatus
    message: str | None
    items: list[TrendItemRead]


class RatioItemRead(BaseModel):
    code: str
    name: str
    category: str
    formula: str
    last_value: float | None = None
    previous_value: float | None = None
    abs_change: float | None = None
    pct_change: float | None = None
    payload: dict = Field(default_factory=dict)


class RatioResults(BaseModel):
    status: ProcedureStatus | None = None
    message: str | None = None
    items: list[RatioItemRead]


class AnalysisConclusion(BaseModel):
    summary: str
    highlights: list[str]
    limitations: list[str]


class LayeredNarrative(BaseModel):
    brief: str
    details: list[str] = []
    technical: list[str] = []


class AnalysisResults(BaseModel):
    run: AnalysisDetail
    anomalies: AnomalyResults | None = None
    correlation: CorrelationResults | None = None
    clustering: ClusterResults | None = None
    forecast: ForecastResults | None = None
    assessment: AssessmentResults | None = None
    trends: TrendResults | None = None
    ratios: RatioResults | None = None
    findings: list[dict] = Field(default_factory=list)
    alerts: list[dict] = Field(default_factory=list)
    conclusion: AnalysisConclusion | None = None
    assessment_narrative: LayeredNarrative | None = None
    anomalies_narrative: LayeredNarrative | None = None
    correlation_narrative: LayeredNarrative | None = None
    clustering_narrative: LayeredNarrative | None = None
    forecast_narrative: LayeredNarrative | None = None

