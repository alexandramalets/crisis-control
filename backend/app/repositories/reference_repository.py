import calendar
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Category, Indicator, Period
from app.models.enums import PeriodGranularity

_MONTHS_IN_PERIOD = {PeriodGranularity.MONTH: 1, PeriodGranularity.QUARTER: 3, PeriodGranularity.YEAR: 12}


def period_end(granularity: PeriodGranularity, start: date) -> date:
    last_month = start.month + _MONTHS_IN_PERIOD[granularity] - 1
    return date(start.year, last_month, calendar.monthrange(start.year, last_month)[1])


class ReferenceRepository:
    def __init__(self, session: Session):
        self.session = session

    def visible_indicators(self, user_id: int | None):
        """Системные показатели и показатели пользователя."""
        query = select(Indicator)
        if user_id is not None:
            query = query.where(or_(Indicator.owner_id.is_(None), Indicator.owner_id == user_id))
        return query

    def list_indicators(self, user_id: int | None) -> list[Indicator]:
        query = self.visible_indicators(user_id).order_by(Indicator.owner_id.nulls_first(), Indicator.code)
        return list(self.session.scalars(query))

    def indicators_by_code(self, codes: set[str], user_id: int) -> dict[str, Indicator]:
        """Пользовательский показатель с тем же кодом имеет приоритет над системным."""
        query = self.visible_indicators(user_id).where(Indicator.code.in_(codes))
        result: dict[str, Indicator] = {}
        for indicator in self.session.scalars(query.order_by(Indicator.owner_id.nulls_first())):
            result[indicator.code] = indicator
        return result

    def ensure_periods(self, granularity: PeriodGranularity, starts: set[date]) -> dict[date, int]:
        rows = [{"granularity": granularity, "start_date": start, "end_date": period_end(granularity, start)}
                for start in sorted(starts)]
        self.session.execute(insert(Period).values(rows).on_conflict_do_nothing(
            index_elements=["granularity", "start_date"]))
        query = select(Period.start_date, Period.id).where(
            Period.granularity == granularity, Period.start_date.in_(starts))
        return dict(self.session.execute(query).tuples().all())

    def ensure_categories(self, organization_id: int, names: set[str]) -> dict[str, int]:
        if not names:
            return {}
        rows = [{"organization_id": organization_id, "name": name} for name in sorted(names)]
        self.session.execute(insert(Category).values(rows).on_conflict_do_nothing(
            index_elements=["organization_id", "name"]))
        query = select(Category.name, Category.id).where(
            Category.organization_id == organization_id, Category.name.in_(names))
        return dict(self.session.execute(query).tuples().all())
