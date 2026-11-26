from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class FindingRead(ORMModel):
    id: int
    organization_id: int
    run_id: int
    code: str
    title: str
    description: str
    severity: str
    confidence: str
    period_label: str | None
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AlertRead(ORMModel):
    id: int
    organization_id: int
    run_id: int
    indicator_code: str | None
    level: str
    rule_code: str
    message: str
    basis: str
    action: str | None
    period_label: str | None
    created_at: datetime


class RecommendationRead(ORMModel):
    id: int
    organization_id: int
    run_id: int
    finding_id: int | None
    title: str
    problem: str
    basis: str
    actions: str
    expected_result: str | None
    limitations: str | None
    priority: str
    status: str
    created_at: datetime


class RecommendationUpdate(BaseModel):
    status: Literal["accepted", "rejected", "proposed"]
    comment: str | None = None


class RecommendationConvert(BaseModel):
    due_at: date | None = None
    assignee_id: int | None = None


class MeasureRead(ORMModel):
    id: int
    organization_id: int
    created_by: int
    assignee_id: int | None
    run_id: int | None
    recommendation_id: int | None
    title: str
    description: str
    expected_result: str | None
    success_criterion: str | None
    actual_result: str | None
    priority: str
    status: str
    due_at: date | None
    indicator_codes: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime | None = None


class MeasureCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    expected_result: str | None = None
    success_criterion: str | None = None
    priority: Literal["low", "medium", "high"] = "medium"
    due_at: date | None = None
    assignee_id: int | None = None
    run_id: int | None = None
    finding_id: int | None = None
    indicator_codes: list[str] = Field(default_factory=list)


class MeasureUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    expected_result: str | None = None
    success_criterion: str | None = None
    actual_result: str | None = None
    priority: Literal["low", "medium", "high"] | None = None
    status: Literal["planned", "in_progress", "done", "overdue", "cancelled"] | None = None
    due_at: date | None = None
    assignee_id: int | None = None
    indicator_codes: list[str] | None = None
    comment: str | None = None


class MeasureEventRead(ORMModel):
    id: int
    measure_id: int
    user_id: int | None
    event_type: str
    comment: str | None
    payload: dict[str, Any] | None = None
    created_at: datetime


class TargetRead(BaseModel):
    id: int
    indicator_code: str | None = None
    kind: str
    value: Decimal
    source: str | None = None
    notes: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None


class ThresholdRead(BaseModel):
    indicator_code: str | None = None
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    source: str | None = None
    notes: str | None = None
    methodology: str | None = None


class TargetUpsert(BaseModel):
    indicator_code: str
    kind: Literal["plan", "norm", "target"]
    value: Decimal
    source: str | None = None
    notes: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None


class ThresholdUpsert(BaseModel):
    indicator_code: str
    lower_bound: Decimal | None = None
    upper_bound: Decimal | None = None
    source: str | None = None
    notes: str | None = None
    methodology: str | None = None


class ScenarioAdjustment(BaseModel):
    indicator_code: str
    percent_change: float


class ScenarioCreate(BaseModel):
    base_run_id: int
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    adjustments: list[ScenarioAdjustment]


class ScenarioRead(ORMModel):
    id: int
    organization_id: int
    created_by: int
    base_run_id: int
    name: str
    description: str | None
    adjustments: list
    result: dict[str, Any] | None = None
    created_at: datetime
