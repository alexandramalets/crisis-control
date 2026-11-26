from typing import Literal

from pydantic import Field, model_validator

from app.core.errors import ServiceError
from app.schemas.common import DataPayload


class AnomalyRequest(DataPayload):
    method: Literal["robust_z", "zscore", "isolation_forest"] = "robust_z"
    threshold: float = Field(3.0, gt=0, le=10)
    min_observations: int = Field(6, ge=3, le=24)


class CorrelationRequest(DataPayload):
    method: Literal["pearson", "spearman"] = "pearson"
    min_observations: int = Field(4, ge=3, le=24)


class ClusteringRequest(DataPayload):
    k: int | Literal["auto"] = "auto"
    k_min: int = Field(2, ge=2, le=10)
    k_max: int = Field(6, ge=2, le=15)

    @model_validator(mode="after")
    def k_range(self):
        if isinstance(self.k, int) and self.k < 1:
            raise ValueError("k должно быть положительным или auto")
        if self.k_max < self.k_min:
            raise ValueError("k_max не может быть меньше k_min")
        return self


class ForecastRequest(DataPayload):
    horizon: int = Field(3, ge=1, le=24)
    model: Literal["auto", "ses", "holt", "seasonal"] = "auto"


class AssessmentRequest(DataPayload):
    pass


class AnalyzeRequest(DataPayload):
    anomalies: dict | None = None
    correlation: dict | None = None
    clustering: dict | None = None
    forecast: dict | None = None
    assessment: dict | None = None
    procedures: list[Literal[
        "validate", "ratios", "anomalies", "trends", "correlation", "clustering", "forecast", "assessment"
    ]] | None = None


def require_frame(payload: DataPayload):
    from app.methods.frame import build_frame

    errors = payload.length_errors()
    if errors:
        raise ServiceError("Набор данных не прошёл проверку", details={"errors": errors}, code="invalid_data")
    return build_frame(payload)
