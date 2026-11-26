from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Organization, OrganizationAccess, User
from app.models.enums import OrganizationAccessLevel
from app.repositories.audit_repository import AuditRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import UserRepository
from app.schemas.admin import OrganizationMemberRead
from app.schemas.common import Page
from app.schemas.organization import (
    OrganizationCreate, OrganizationEmployeeCreate, OrganizationRead, OrganizationSummary, OrganizationUpdate,
)
from app.services.access import AccessContext
from app.services.errors import ConflictError, NotFoundError, PermissionDeniedError, ValidationFailedError

NOT_FOUND = "Организация не найдена"
NAME_TAKEN = "Организация с таким названием уже существует"
USER_NOT_FOUND = "Пользователь не найден"
ACCESS_MISSING = "У сотрудника нет доступа к этой организации"
EDIT_REQUIRED = (
    "Недостаточно прав: загрузка данных и запуск анализа доступны "
    "владельцу организации или сотруднику с правом «редактирование»"
)
OWNER_ACCESS = "Нельзя отозвать доступ владельца организации. Сначала смените владельца вне этой операции."
MANAGE_MEMBERS = "Назначать сотрудников может администратор системы или владелец организации."
CLEAR_WORKSPACE = (
    "Будут удалены все наборы данных организации, связанные исследования и отчёты. "
    "Карточка организации и список сотрудников сохраняются."
)


def _level_value(level) -> str:
    if level is None:
        return OrganizationAccessLevel.VIEW.value
    return level.value if hasattr(level, "value") else str(level)


class OrganizationService:
    def __init__(self, session: Session):
        self.session = session
        self.organizations = OrganizationRepository(session)
        self.users = UserRepository(session)
        self.audit = AuditRepository(session)

    def get_visible(self, ctx: AccessContext, organization_id: int) -> Organization:
        organization = self.organizations.get(organization_id, ctx.read_scope)
        if organization is None:
            raise NotFoundError(NOT_FOUND)
        return organization

    def get_modifiable(self, ctx: AccessContext, organization_id: int) -> Organization:
        organization = self.get_visible(ctx, organization_id)
        if not self.can_edit(ctx, organization):
            raise PermissionDeniedError(EDIT_REQUIRED)
        return organization

    def can_edit(self, ctx: AccessContext, organization: Organization) -> bool:
        if organization.owner_id == ctx.user_id:
            return True
        row = self.organizations.get_access(organization.id, ctx.user_id)
        return row is not None and _level_value(row.access_level) == OrganizationAccessLevel.EDIT.value

    def to_read(self, ctx: AccessContext, organization: Organization) -> OrganizationRead:
        can_edit = self.can_edit(ctx, organization)
        row = self.organizations.get_access(organization.id, ctx.user_id)
        if organization.owner_id == ctx.user_id:
            level = OrganizationAccessLevel.EDIT.value
        elif row is not None:
            level = _level_value(row.access_level)
        else:
            level = OrganizationAccessLevel.VIEW.value
        return OrganizationRead(
            id=organization.id,
            owner_id=organization.owner_id,
            name=organization.name,
            description=organization.description,
            created_at=organization.created_at,
            access_level=level,
            can_edit=can_edit,
        )

    def to_summary(self, ctx: AccessContext, organization: Organization, stats: dict | None = None) -> OrganizationSummary:
        base = self.to_read(ctx, organization)
        stats = stats or self.organizations.workspace_stats([organization.id]).get(organization.id, {})
        return OrganizationSummary(**base.model_dump(), **{
            "members_count": stats.get("members_count", 0),
            "datasets_count": stats.get("datasets_count", 0),
            "analyses_count": stats.get("analyses_count", 0),
            "last_analysis_at": stats.get("last_analysis_at"),
        })

    def search(self, ctx: AccessContext, limit: int, offset: int) -> Page[OrganizationSummary]:
        items, total = self.organizations.find(ctx.read_scope, limit, offset)
        stats = self.organizations.workspace_stats([item.id for item in items])
        return Page(
            items=[self.to_summary(ctx, item, stats.get(item.id, {})) for item in items],
            total=total, limit=limit, offset=offset,
        )

    def summary(self, ctx: AccessContext, organization_id: int) -> OrganizationSummary:
        return self.to_summary(ctx, self.get_visible(ctx, organization_id))

    def ensure_can_manage_members(self, ctx: AccessContext, organization: Organization) -> None:
        if ctx.is_admin or organization.owner_id == ctx.user_id:
            return
        raise PermissionDeniedError(MANAGE_MEMBERS)

    def create(self, ctx: AccessContext, data: OrganizationCreate) -> Organization:
        if self.organizations.name_taken(ctx.user_id, data.name):
            raise ConflictError(NAME_TAKEN)
        organization = self.organizations.add(Organization(owner_id=ctx.user_id, **data.model_dump()))
        self.organizations.grant(OrganizationAccess(
            organization_id=organization.id, user_id=ctx.user_id, granted_by=ctx.user_id,
            access_level=_level_value(OrganizationAccessLevel.EDIT),
        ))
        self.audit.add(
            "organization_created", ctx.user_id, "organization", organization.id,
            organization_id=organization.id,
        )
        self.session.commit()
        return organization

    def update(self, ctx: AccessContext, organization_id: int, data: OrganizationUpdate) -> Organization:
        organization = self.get_modifiable(ctx, organization_id)
        changes = data.model_dump(exclude_unset=True)
        if changes.get("name") is None:
            changes.pop("name", None)
        if "name" in changes and self.organizations.name_taken(ctx.user_id, changes["name"], organization.id):
            raise ConflictError(NAME_TAKEN)
        for field, value in changes.items():
            setattr(organization, field, value)
        self.session.commit()
        return organization

    def delete(self, ctx: AccessContext, organization_id: int) -> None:
        organization = self.get_modifiable(ctx, organization_id)
        self.organizations.delete(organization)
        self.audit.add(
            "organization_deleted", ctx.user_id, "organization", organization_id,
            organization_id=organization_id,
        )
        self.session.commit()

    def grant_access(
        self,
        ctx: AccessContext,
        organization_id: int,
        user_id: int,
        access_level: OrganizationAccessLevel = OrganizationAccessLevel.VIEW,
    ) -> OrganizationAccess:
        organization = self.get_visible(ctx, organization_id)
        self.ensure_can_manage_members(ctx, organization)
        user = self.users.get(user_id)
        if user is None:
            raise ValidationFailedError(USER_NOT_FOUND)
        level = _level_value(access_level)
        if organization.owner_id == user_id:
            level = OrganizationAccessLevel.EDIT.value
        existing = self.organizations.get_access(organization_id, user_id)
        if existing is not None:
            existing.access_level = level
            existing.granted_by = ctx.user_id
            self.audit.add(
                "organization_access_updated", ctx.user_id, "user", user_id,
                organization_id=organization_id,
            )
            self.session.commit()
            self.session.refresh(existing)
            return existing
        access = self.organizations.grant(OrganizationAccess(
            organization_id=organization_id, user_id=user_id, granted_by=ctx.user_id,
            access_level=level,
        ))
        self.audit.add(
            "organization_access_granted", ctx.user_id, "user", user_id,
            organization_id=organization_id,
        )
        self.session.commit()
        return access

    def assign_member(self, ctx: AccessContext, organization_id: int, user_id: int | None,
                      login: str | None, access_level: OrganizationAccessLevel) -> OrganizationMemberRead:
        resolved_id = user_id
        if resolved_id is None:
            if not login or not str(login).strip():
                raise ValidationFailedError("Укажите сотрудника: выберите учётную запись или введите логин/почту")
            user = self.users.get_by_login(login)
            if user is None:
                raise ValidationFailedError(
                    "Пользователь не найден. Создайте учётную запись или укажите точный логин/почту."
                )
            resolved_id = user.id
        self.grant_access(ctx, organization_id, resolved_id, access_level)
        members = self.member_reads(ctx, organization_id)
        match = next((item for item in members if item.user_id == resolved_id), None)
        if match is None:
            raise NotFoundError("Сотрудник не появился в списке организации. Повторите назначение.")
        return match

    def create_employee(self, ctx: AccessContext, organization_id: int,
                        data: OrganizationEmployeeCreate) -> OrganizationMemberRead:
        from app.services.user_service import UserService
        organization = self.get_visible(ctx, organization_id)
        self.ensure_can_manage_members(ctx, organization)
        user = UserService(self.session).create_user(
            data.username, data.email, data.full_name, data.password, "analyst",
        )
        return self.assign_member(
            ctx, organization_id, user.id, None, OrganizationAccessLevel(data.access_level),
        )

    def revoke_access(self, ctx: AccessContext, organization_id: int, user_id: int) -> None:
        organization = self.get_visible(ctx, organization_id)
        self.ensure_can_manage_members(ctx, organization)
        if organization.owner_id == user_id:
            raise ValidationFailedError(OWNER_ACCESS)
        if not self.organizations.revoke(organization_id, user_id):
            raise NotFoundError(ACCESS_MISSING)
        self.audit.add(
            "organization_access_revoked", ctx.user_id, "user", user_id,
            organization_id=organization_id,
        )
        self.session.commit()

    def list_members(self, ctx: AccessContext, organization_id: int) -> list[int]:
        self.get_visible(ctx, organization_id)
        return [row.user_id for row in self.organizations.list_access(organization_id)]

    def member_reads(self, ctx: AccessContext, organization_id: int) -> list[OrganizationMemberRead]:
        organization = self.get_visible(ctx, organization_id)
        rows = self.organizations.list_access(organization_id)
        user_ids = [row.user_id for row in rows]
        users = {}
        if user_ids:
            users = {user.id: user for user in self.session.scalars(select(User).where(User.id.in_(user_ids)))}
        members = []
        for row in rows:
            user = users.get(row.user_id)
            if user is None:
                continue
            members.append(OrganizationMemberRead(
                user_id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                role=user.role.code,
                granted_at=row.granted_at,
                access_level=(
                    row.access_level.value if hasattr(row.access_level, "value") else str(row.access_level or "view")
                ),
                is_owner=organization.owner_id == user.id,
                is_active=user.is_active,
            ))
        return members

    def clear_workspace(self, ctx: AccessContext, organization_id: int) -> dict:
        """Удаляет наборы и исследования организации, не трогая карточку и сотрудников."""
        organization = self.get_modifiable(ctx, organization_id)
        datasets = self.organizations.datasets_of(organization.id)
        from app.core.config import get_settings
        from app.services.ingest.storage import FileStorage
        storage = FileStorage(get_settings())
        removed = 0
        for dataset in datasets:
            storage.delete_dataset_file(dataset.id)
            self.session.delete(dataset)
            removed += 1
        self.audit.add(
            "organization_workspace_cleared", ctx.user_id, "organization", organization_id,
            organization_id=organization_id,
        )
        self.session.commit()
        return {"organization_id": organization_id, "datasets_deleted": removed, "note": CLEAR_WORKSPACE}
