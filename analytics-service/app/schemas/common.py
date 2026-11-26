from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ProcedureStatus = Literal["ok", "skipped", "error"]
ImpactDirection = Literal["higher_better", "lower_better", "neutral"]


class ORMModel(BaseModel):
    model_config = ConfigDict(ser_json_inf_nan="null")


class IndicatorSeries(BaseModel):
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z][A-Za-z0-9_]*$")
    values: list[float | None] = Field(min_length=1)
    impact_direction: ImpactDirection = "neutral"
    weight: float | None = Field(None, ge=0)
    lower_bound: float | None = None
    upper_bound: float | None = None


class DataPayload(BaseModel):
    request_id: str | None = Field(None, max_length=64)
    random_state: int = Field(42, ge=0)
    periods: list[str] = Field(min_length=1, max_length=240)
    indicators: list[IndicatorSeries] = Field(min_length=1, max_length=40)

    def length_errors(self) -> list[str]:
        n = len(self.periods)
        errors = []
        if len(set(self.periods)) != n:
            errors.append("Периоды не должны повторяться")
        codes = [item.code for item in self.indicators]
        if len(set(codes)) != len(codes):
            errors.append("Коды показателей должны быть уникальны")
        for item in self.indicators:
            if len(item.values) != n:
                errors.append(
                    f"Показатель {item.code}: {len(item.values)} значений при {n} периодах"
                )
        return errors


class ProcedureResult(ORMModel):
    status: ProcedureStatus
    message: str | None = None
    warnings: list[str] = Field(default_factory=list)
    result: dict[str, Any] | None = None
