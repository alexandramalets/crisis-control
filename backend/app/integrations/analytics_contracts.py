"""DTO контракта /analytics/v1. Не зависят от доменной модели PostgreSQL."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ProcedureStatus = Literal["ok", "skipped", "error"]
ML_PROCEDURES = (
    "validate", "ratios", "anomalies", "trends", "correlation", "clustering", "forecast", "assessment",
)


class ProcedureEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: ProcedureStatus
    message: str | None = None
    warnings: list[str] = Field(default_factory=list)
    result: dict[str, Any] | None = None


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    service_version: str | None = None
    request_id: str | None = None
    random_state: int | None = None
    procedures: dict[str, ProcedureEnvelope]
