from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.models.enums import AnalysisStatus, ImpactDirection, PeriodGranularity, ProcedureStatus


class DashboardPeriod(BaseModel):
    start: date
    end: date
    months: int


class DashboardRef(BaseModel):
    id: int
    name: str


class SeriesPoint(BaseModel):
    period_start: date
    label: str
    value: float | None = None
    lower: float | None = None
    upper: float | None = None
    kind: Literal["history", "forecast"] = "history"


class MetricCardData(BaseModel):
    code: str
    name: str
    unit: str
    impact_direction: ImpactDirection
    value: Decimal | None = None
    previous_value: Decimal | None = None
    change_percent: float | None = None
    change_direction: Literal["up", "down"] | None = None
    change_favorable: bool | None = None
    sparkline: list[SeriesPoint]


class IndicatorSeries(BaseModel):
    code: str
    name: str
    history: list[SeriesPoint]
    forecast: list[SeriesPoint]


class AssessmentGroup(BaseModel):
    code: str
    name: str
    score: float


class AssessmentFactor(BaseModel):
    code: str
    name: str
    normalized_score: Decimal
    explanation: str | None = None


class DashboardAssessment(BaseModel):
    status: ProcedureStatus | Literal["missing"]
    score: Decimal | None = None
    history_score: Decimal | None = None
    compliance_score: Decimal | None = None
    completeness: Decimal | None = None
    interpretation: str | None = None
    warning: str | None = None
    groups: list[AssessmentGroup]
    factors: list[AssessmentFactor]


class DashboardAnomaly(BaseModel):
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


class DashboardCorrelationPair(BaseModel):
    indicator_a: str
    indicator_b: str
    coefficient: float | None
    n_observations: int


class DashboardCorrelations(BaseModel):
    indicators: list[str]
    names: dict[str, str]
    pairs: list[DashboardCorrelationPair]
    interpretation: str


class DashboardRun(BaseModel):
    id: int
    dataset_id: int
    dataset_name: str
    status: AnalysisStatus
    created_at: datetime
    finished_at: datetime | None


class OrganizationSnapshot(BaseModel):
    id: int
    name: str
    dataset_name: str | None = None
    analysis_run_id: int | None = None
    score: Decimal | None = None
    interpretation: str | None = None
    last_analysis_at: datetime | None = None


class DashboardResponse(BaseModel):
    empty: bool
    message: str | None = None
    organization: DashboardRef | None = None
    dataset: DashboardRef | None = None
    granularity: PeriodGranularity | None = None
    period: DashboardPeriod | None = None
    analysis_run_id: int | None = None
    cards: list[MetricCardData]
    series: list[IndicatorSeries]
    assessment: DashboardAssessment | None = None
    anomalies: list[DashboardAnomaly]
    correlations: DashboardCorrelations | None = None
    recent_runs: list[DashboardRun]
    organization_snapshots: list[OrganizationSnapshot] = []
    alerts_count: int = 0
    findings_count: int = 0
    open_measures: int = 0
    overdue_measures: int = 0
    proposed_recommendations: int = 0
    workspace_state: str | None = None
