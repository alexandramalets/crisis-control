from sqlalchemy import select
from sqlalchemy.orm import Session, undefer

from app.models import AnalysisRun, Dataset, Organization, Report
from app.repositories.base import paginate
from app.repositories.visibility import visible_organization_clause


class ReportRepository:
    def __init__(self, session: Session):
        self.session = session

    def _scoped(self, owner_id: int | None):
        query = select(Report)
        clause = visible_organization_clause(owner_id)
        if clause is not None:
            query = (
                query.join(AnalysisRun, AnalysisRun.id == Report.run_id)
                .join(Dataset, Dataset.id == AnalysisRun.dataset_id)
                .join(Organization, Organization.id == Dataset.organization_id)
                .where(clause)
            )
        return query

    def find(self, owner_id: int | None, run_id: int | None, limit: int, offset: int) -> tuple[list[Report], int]:
        query = self._scoped(owner_id)
        if run_id is not None:
            query = query.where(Report.run_id == run_id)
        return paginate(self.session, query.order_by(Report.created_at.desc(), Report.id.desc()), limit, offset)

    def get(self, report_id: int, owner_id: int | None, with_content: bool = False) -> Report | None:
        query = self._scoped(owner_id).where(Report.id == report_id)
        if with_content:
            query = query.options(undefer(Report.content))
        return self.session.scalar(query)

    def add(self, report: Report) -> Report:
        self.session.add(report)
        self.session.flush()
        return report
