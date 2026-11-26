from sqlalchemy import or_, select

from app.models import Organization, OrganizationAccess


def visible_organization_clause(user_id: int | None):
    """Фильтр организаций: администратор (user_id is None) видит все;
    сотрудник — организации, которыми владеет или к которым назначен доступ."""
    if user_id is None:
        return None
    assigned = select(OrganizationAccess.organization_id).where(OrganizationAccess.user_id == user_id)
    return or_(Organization.owner_id == user_id, Organization.id.in_(assigned))
