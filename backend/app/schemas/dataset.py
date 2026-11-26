import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from app.models.enums import IssueSeverity, PeriodGranularity
from app.schemas.common import ORMModel

MAX_VALUES_PER_DATASET = 100_000

IndicatorCode = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[a-z][a-z0-9_]{0,49}$")]
CategoryName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Amount = Annotated[Decimal, Field(max_digits=20, decimal_places=4, allow_inf_nan=False)]


class IndicatorValueIn(BaseModel):
    indicator_code: IndicatorCode
    period_start: date = Field(description="Первый день периода, например 2024-01-01")
    category: CategoryName | None = None
    value: Amount | None = Field(description="null — пропуск в исходных данных")


class DatasetCreate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    granularity: PeriodGranularity = PeriodGranularity.MONTH
    values: list[IndicatorValueIn] = Field(min_length=1, max_length=MAX_VALUES_PER_DATASET)

    @field_validator("values")
    @classmethod
    def unique_cells(cls, values: list[IndicatorValueIn]) -> list[IndicatorValueIn]:
        seen = set()
        for index, item in enumerate(values):
            key = (item.indicator_code, item.period_start, item.category)
            if key in seen:
                raise ValueError(
                    f"Повтор значения в элементе {index}: показатель {item.indicator_code}, "
                    f"период {item.period_start}, категория {item.category or '—'}"
                )
            seen.add(key)
        return values

    @model_validator(mode="after")
    def periods_aligned(self):
        allowed_months = {
            PeriodGranularity.MONTH: range(1, 13),
            PeriodGranularity.QUARTER: (1, 4, 7, 10),
            PeriodGranularity.YEAR: (1,),
        }[self.granularity]
        for index, item in enumerate(self.values):
            if item.period_start.day != 1 or item.period_start.month not in allowed_months:
                raise ValueError(
                    f"Элемент {index}: дата {item.period_start} не является началом периода "
                    f"для периодичности «{self.granularity.value}»"
                )
        return self


class DatasetIssueRead(ORMModel):
    severity: IssueSeverity
    code: str
    row_number: int | None
    column_name: str | None
    message: str


class DatasetSummary(ORMModel):
    id: int
    organization_id: int
    uploaded_by: int
    name: str
    source_filename: str | None
    granularity: PeriodGranularity
    version_no: int = 1
    predecessor_id: int | None = None
    created_at: datetime


class DatasetIndicatorRead(BaseModel):
    id: int
    code: str
    name: str
    unit: str
    values_count: int
    missing_count: int


class DatasetDetail(DatasetSummary):
    source_sha256: str
    period_from: date | None
    period_to: date | None
    periods_count: int
    values_count: int
    categories: list[str]
    indicators: list[DatasetIndicatorRead]
    issues: list[DatasetIssueRead]


class IndicatorValueRead(BaseModel):
    indicator_code: str
    period_start: date
    category: str | None
    value: Decimal | None


class DatasetImportRequest(BaseModel):
    staging_id: uuid.UUID | None = None
    staging_ids: list[uuid.UUID] | None = None
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    period_column: str | None = Field(None, description="Столбец периода; по умолчанию определяется автоматически")
    indicator_columns: list[str] | None = Field(
        None, description="Столбцы показателей; по умолчанию — все распознанные столбцы справочника",
    )
    category_column: str | None = None
    granularity: PeriodGranularity | None = None
    merge_previous: bool = True

    @model_validator(mode="after")
    def collect_staging(self):
        ids: list[uuid.UUID] = []
        if self.staging_id is not None:
            ids.append(self.staging_id)
        for item in self.staging_ids or []:
            if item not in ids:
                ids.append(item)
        if not ids:
            raise ValueError("Укажите хотя бы один загруженный файл")
        self.staging_ids = ids
        self.staging_id = ids[0]
        return self


class DatasetValidateRequest(BaseModel):
    staging_id: uuid.UUID
    period_column: str | None = None
    indicator_columns: list[str] | None = None
    category_column: str | None = None
    granularity: PeriodGranularity | None = None


class TemplateFormat(BaseModel):
    format: Literal["csv", "xlsx"] = "csv"
