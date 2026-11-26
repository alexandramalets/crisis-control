from pydantic import Field, computed_field

from app.models.enums import ImpactDirection
from app.schemas.common import ORMModel


class UnitRead(ORMModel):
    code: str
    name: str
    symbol: str


class IndicatorGroupRead(ORMModel):
    code: str
    name: str


class IndicatorRead(ORMModel):
    id: int
    code: str
    name: str
    impact_direction: ImpactDirection
    description: str | None
    unit: UnitRead
    group: IndicatorGroupRead
    owner_id: int | None = Field(exclude=True)

    @computed_field
    @property
    def is_system(self) -> bool:
        return self.owner_id is None
