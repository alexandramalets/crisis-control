from datetime import date

from sqlalchemy import case, func, insert, select
from sqlalchemy.orm import Session

from app.models import (
    Category, Dataset, DatasetIssue, Indicator, IndicatorValue, Organization, Period, Unit,
)
from app.repositories.base import paginate
from app.repositories.visibility import visible_organization_clause


class DatasetRepository:
    def __init__(self, session: Session):
        self.session = session

    def _scoped(self, user_id: int | None):
        query = select(Dataset)
        clause = visible_organization_clause(user_id)
        if clause is not None:
            query = query.join(Organization, Organization.id == Dataset.organization_id).where(clause)
        return query

    def find(self, owner_id: int | None, organization_id: int | None,
             limit: int, offset: int) -> tuple[list[Dataset], int]:
        query = self._scoped(owner_id)
        if organization_id is not None:
            query = query.where(Dataset.organization_id == organization_id)
        return paginate(self.session, query.order_by(Dataset.created_at.desc(), Dataset.id.desc()), limit, offset)

    def get(self, dataset_id: int, owner_id: int | None) -> Dataset | None:
        return self.session.scalar(self._scoped(owner_id).where(Dataset.id == dataset_id))

    def name_taken(self, organization_id: int, name: str) -> bool:
        query = select(Dataset.id).where(Dataset.organization_id == organization_id, Dataset.name == name)
        return self.session.scalar(query.limit(1)) is not None

    def latest_by_name(self, organization_id: int, name: str) -> Dataset | None:
        query = (
            select(Dataset)
            .where(Dataset.organization_id == organization_id, Dataset.name == name)
            .order_by(Dataset.version_no.desc(), Dataset.id.desc())
            .limit(1)
        )
        return self.session.scalar(query)

    def add(self, dataset: Dataset) -> Dataset:
        self.session.add(dataset)
        self.session.flush()
        return dataset

    def add_values(self, rows: list[dict]) -> None:
        for start in range(0, len(rows), 5000):
            self.session.execute(insert(IndicatorValue), rows[start:start + 5000])

    def add_issues(self, issues: list[DatasetIssue]) -> None:
        self.session.add_all(issues)

    def delete(self, dataset: Dataset) -> None:
        self.session.delete(dataset)
        self.session.flush()

    def issues(self, dataset_id: int) -> list[DatasetIssue]:
        query = select(DatasetIssue).where(DatasetIssue.dataset_id == dataset_id).order_by(DatasetIssue.id)
        return list(self.session.scalars(query))

    def indicator_stats(self, dataset_id: int) -> list[dict]:
        query = (
            select(
                Indicator.id, Indicator.code, Indicator.name, Unit.symbol.label("unit"),
                func.count().label("values_count"),
                func.count(case((IndicatorValue.value.is_(None), 1))).label("missing_count"),
            )
            .join(Indicator, Indicator.id == IndicatorValue.indicator_id)
            .join(Unit, Unit.id == Indicator.unit_id)
            .where(IndicatorValue.dataset_id == dataset_id)
            .group_by(Indicator.id, Unit.symbol)
            .order_by(Indicator.code)
        )
        return [dict(row._mapping) for row in self.session.execute(query)]

    def period_range(self, dataset_id: int) -> tuple[date | None, date | None, int]:
        query = (
            select(func.min(Period.start_date), func.max(Period.start_date), func.count(Period.id.distinct()))
            .join(IndicatorValue, IndicatorValue.period_id == Period.id)
            .where(IndicatorValue.dataset_id == dataset_id)
        )
        return tuple(self.session.execute(query).one())

    def categories(self, dataset_id: int) -> list[str]:
        query = (
            select(Category.name).distinct()
            .join(IndicatorValue, IndicatorValue.category_id == Category.id)
            .where(IndicatorValue.dataset_id == dataset_id)
            .order_by(Category.name)
        )
        return list(self.session.scalars(query))

    def values(self, dataset_id: int, indicator_codes: list[str] | None, period_from: date | None,
               period_to: date | None, limit: int, offset: int) -> tuple[list, int]:
        query = (
            select(Indicator.code.label("indicator_code"), Period.start_date.label("period_start"),
                   Category.name.label("category"), IndicatorValue.value)
            .join(Indicator, Indicator.id == IndicatorValue.indicator_id)
            .join(Period, Period.id == IndicatorValue.period_id)
            .outerjoin(Category, Category.id == IndicatorValue.category_id)
            .where(IndicatorValue.dataset_id == dataset_id)
        )
        if indicator_codes:
            query = query.where(Indicator.code.in_(indicator_codes))
        if period_from:
            query = query.where(Period.start_date >= period_from)
        if period_to:
            query = query.where(Period.start_date <= period_to)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        query = query.order_by(Period.start_date, Indicator.code, Category.name.nulls_first())
        rows = self.session.execute(query.limit(limit).offset(offset)).mappings().all()
        return list(rows), total or 0
