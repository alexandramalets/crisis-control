from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AnalysisRun, Dataset, Organization, OrganizationAccess
from app.repositories.base import paginate
from app.repositories.visibility import visible_organization_clause


class OrganizationRepository:
    def __init__(self, session: Session):
        self.session = session

    def _scoped(self, user_id: int | None):
        query = select(Organization)
        clause = visible_organization_clause(user_id)
        if clause is not None:
            query = query.where(clause)
        return query

    def find(self, user_id: int | None, limit: int, offset: int) -> tuple[list[Organization], int]:
        return paginate(self.session, self._scoped(user_id).order_by(Organization.name, Organization.id),
                        limit, offset)

    def get(self, organization_id: int, user_id: int | None) -> Organization | None:
        return self.session.scalar(self._scoped(user_id).where(Organization.id == organization_id))

    def get_unscoped(self, organization_id: int) -> Organization | None:
        return self.session.get(Organization, organization_id)

    def name_taken(self, owner_id: int, name: str, exclude_id: int | None = None) -> bool:
        query = select(Organization.id).where(Organization.owner_id == owner_id, Organization.name == name)
        if exclude_id is not None:
            query = query.where(Organization.id != exclude_id)
        return self.session.scalar(query.limit(1)) is not None

    def add(self, organization: Organization) -> Organization:
        self.session.add(organization)
        self.session.flush()
        return organization

    def delete(self, organization: Organization) -> None:
        self.session.delete(organization)
        self.session.flush()

    def has_access(self, organization_id: int, user_id: int) -> bool:
        query = select(OrganizationAccess.user_id).where(
            OrganizationAccess.organization_id == organization_id, OrganizationAccess.user_id == user_id)
        return self.session.scalar(query.limit(1)) is not None

    def get_access(self, organization_id: int, user_id: int) -> OrganizationAccess | None:
        return self.session.get(OrganizationAccess, (organization_id, user_id))

    def list_access(self, organization_id: int) -> list[OrganizationAccess]:
        query = select(OrganizationAccess).where(OrganizationAccess.organization_id == organization_id)
        return list(self.session.scalars(query))

    def list_access_for_user(self, user_id: int) -> list[OrganizationAccess]:
        query = select(OrganizationAccess).where(OrganizationAccess.user_id == user_id)
        return list(self.session.scalars(query))

    def grant(self, access: OrganizationAccess) -> OrganizationAccess:
        self.session.add(access)
        self.session.flush()
        return access

    def revoke(self, organization_id: int, user_id: int) -> bool:
        row = self.session.get(OrganizationAccess, (organization_id, user_id))
        if row is None:
            return False
        self.session.delete(row)
        self.session.flush()
        return True

    def members_by_organization(self, organization_ids: list[int]) -> dict[int, list[int]]:
        if not organization_ids:
            return {}
        query = select(OrganizationAccess.organization_id, OrganizationAccess.user_id).where(
            OrganizationAccess.organization_id.in_(organization_ids))
        grouped: dict[int, list[int]] = {organization_id: [] for organization_id in organization_ids}
        for organization_id, user_id in self.session.execute(query):
            grouped.setdefault(organization_id, []).append(user_id)
        return grouped

    def workspace_stats(self, organization_ids: list[int]) -> dict[int, dict]:
        empty = {"members_count": 0, "datasets_count": 0, "analyses_count": 0, "last_analysis_at": None}
        stats = {organization_id: dict(empty) for organization_id in organization_ids}
        if not organization_ids:
            return stats
        member_rows = self.session.execute(
            select(OrganizationAccess.organization_id, func.count())
            .where(OrganizationAccess.organization_id.in_(organization_ids))
            .group_by(OrganizationAccess.organization_id)
        )
        for organization_id, count in member_rows:
            stats[organization_id]["members_count"] = count
        dataset_rows = self.session.execute(
            select(Dataset.organization_id, func.count())
            .where(Dataset.organization_id.in_(organization_ids))
            .group_by(Dataset.organization_id)
        )
        for organization_id, count in dataset_rows:
            stats[organization_id]["datasets_count"] = count
        analysis_rows = self.session.execute(
            select(
                Dataset.organization_id,
                func.count(AnalysisRun.id),
                func.max(AnalysisRun.created_at),
            )
            .join(AnalysisRun, AnalysisRun.dataset_id == Dataset.id)
            .where(Dataset.organization_id.in_(organization_ids))
            .group_by(Dataset.organization_id)
        )
        for organization_id, count, last_at in analysis_rows:
            stats[organization_id]["analyses_count"] = count
            stats[organization_id]["last_analysis_at"] = last_at
        return stats

    def datasets_of(self, organization_id: int) -> list[Dataset]:
        query = select(Dataset).where(Dataset.organization_id == organization_id).order_by(Dataset.id)
        return list(self.session.scalars(query))
