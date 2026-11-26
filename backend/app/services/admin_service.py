from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AnalysisRun, Dataset, Organization, OrganizationAccess, User
from app.models.enums import OrganizationAccessLevel
from app.models.enums import AnalysisStatus
from app.repositories.audit_repository import AuditRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.user_repository import SessionRepository, UserRepository
from app.schemas.admin import (
    AdminOverview, AdminPasswordReset, AdminUserCreate, AdminUserRead, AdminUserUpdate,
    AuditEventRead, OrganizationMemberRead,
)
from app.schemas.auth import validate_password_policy
from app.schemas.common import Page
from app.schemas.organization import OrganizationRead
from app.services.access import AccessContext
from app.services.errors import NotFoundError, ValidationFailedError
from app.services.organization_service import OrganizationService
from app.services.user_service import UserService
from app.core.security import hash_password

USER_NOT_FOUND = "Пользователь не найден"


class AdminService:
    def __init__(self, session: Session):
        self.session = session
        self.users = UserRepository(session)
        self.sessions = SessionRepository(session)
        self.organizations = OrganizationRepository(session)
        self.audit = AuditRepository(session)
        self.user_service = UserService(session)
        self.organization_service = OrganizationService(session)

    def overview(self, ctx: AccessContext) -> AdminOverview:
        ctx.ensure_admin()
        analyses_total = self.session.scalar(select(func.count()).select_from(AnalysisRun)) or 0
        analyses_completed = self.session.scalar(
            select(func.count()).select_from(AnalysisRun).where(
                AnalysisRun.status.in_((AnalysisStatus.COMPLETED, AnalysisStatus.PARTIALLY_COMPLETED)))
        ) or 0
        return AdminOverview(
            users_total=self.users.count(),
            users_active=self.users.count(active_only=True),
            organizations_total=self.session.scalar(select(func.count()).select_from(Organization)) or 0,
            datasets_total=self.session.scalar(select(func.count()).select_from(Dataset)) or 0,
            analyses_total=analyses_total,
            analyses_completed=analyses_completed,
            recent_events=[AuditEventRead.model_validate(item) for item in self.audit.recent(20)],
        )

    def list_users(self, ctx: AccessContext, query: str | None, limit: int, offset: int) -> Page[AdminUserRead]:
        ctx.ensure_admin()
        items, total = self.users.search(query, limit, offset)
        return Page(items=[self._user_read(user) for user in items], total=total, limit=limit, offset=offset)

    def get_user(self, ctx: AccessContext, user_id: int) -> AdminUserRead:
        ctx.ensure_admin()
        return self._user_read(self._require_user(user_id))

    def create_user(self, ctx: AccessContext, data: AdminUserCreate) -> AdminUserRead:
        ctx.ensure_admin()
        user = self.user_service.create_user(data.username, data.email, data.full_name, data.password, data.role)
        if not data.is_active:
            user.is_active = False
        for organization_id in data.organization_ids:
            organization = self.organizations.get_unscoped(organization_id)
            if organization is None:
                raise ValidationFailedError("Организация не найдена", details={"organization_id": organization_id})
            level = OrganizationAccessLevel(data.organization_access_level)
            existing = self.organizations.get_access(organization_id, user.id)
            if existing is not None:
                existing.access_level = level.value
                existing.granted_by = ctx.user_id
            else:
                self.organizations.grant(OrganizationAccess(
                    organization_id=organization_id, user_id=user.id, granted_by=ctx.user_id,
                    access_level=level.value,
                ))
            self.audit.add("organization_access_granted", ctx.user_id, "user", user.id)
        self.audit.add("user_created", ctx.user_id, "user", user.id)
        self.session.commit()
        return self._user_read(user)

    def update_user(self, ctx: AccessContext, user_id: int, data: AdminUserUpdate) -> AdminUserRead:
        ctx.ensure_admin()
        user = self._require_user(user_id)
        changes = data.model_dump(exclude_unset=True)
        if "full_name" in changes and changes["full_name"] is not None:
            user.full_name = changes["full_name"]
        if "role" in changes and changes["role"] is not None:
            role = self.users.get_role(changes["role"])
            if role is None:
                raise ValidationFailedError(f"Неизвестная роль: {changes['role']}")
            user.role = role
            self.audit.add("user_role_changed", ctx.user_id, "user", user.id)
        if "is_active" in changes and changes["is_active"] is not None:
            user.is_active = changes["is_active"]
            if not user.is_active:
                self.sessions.revoke_all_for_user(user.id, datetime.now(UTC))
                self.audit.add("user_blocked", ctx.user_id, "user", user.id)
            else:
                user.locked_until = None
                user.failed_login_count = 0
                self.audit.add("user_unblocked", ctx.user_id, "user", user.id)
        self.session.commit()
        return self._user_read(user)

    def reset_password(self, ctx: AccessContext, user_id: int, data: AdminPasswordReset) -> None:
        ctx.ensure_admin()
        user = self._require_user(user_id)
        try:
            validate_password_policy(data.password, user.username, user.email)
        except ValueError as exc:
            raise ValidationFailedError(str(exc)) from exc
        user.password_hash = hash_password(data.password)
        self.sessions.revoke_all_for_user(user.id, datetime.now(UTC))
        self.audit.add("user_password_reset", ctx.user_id, "user", user.id)
        self.session.commit()

    def unlock_user(self, ctx: AccessContext, user_id: int) -> AdminUserRead:
        ctx.ensure_admin()
        user = self._require_user(user_id)
        user.locked_until = None
        user.failed_login_count = 0
        user.is_active = True
        self.audit.add("user_unlocked", ctx.user_id, "user", user.id)
        self.session.commit()
        return self._user_read(user)

    def organization_members(self, ctx: AccessContext, organization_id: int) -> list[OrganizationMemberRead]:
        ctx.ensure_admin()
        return self.organization_service.member_reads(ctx, organization_id)

    def grant_organization_access(self, ctx: AccessContext, organization_id: int, user_id: int,
                                  access_level: str) -> OrganizationMemberRead:
        ctx.ensure_admin()
        organization = self.organizations.get_unscoped(organization_id)
        if organization is None:
            raise NotFoundError("Организация не найдена")
        self._require_user(user_id)
        level = OrganizationAccessLevel(access_level)
        if organization.owner_id == user_id:
            level = OrganizationAccessLevel.EDIT
        existing = self.organizations.get_access(organization_id, user_id)
        if existing is not None:
            existing.access_level = level.value
            existing.granted_by = ctx.user_id
            self.audit.add(
                "organization_access_updated", ctx.user_id, "user", user_id,
                organization_id=organization_id,
            )
        else:
            self.organizations.grant(OrganizationAccess(
                organization_id=organization_id, user_id=user_id, granted_by=ctx.user_id,
                access_level=level.value,
            ))
            self.audit.add(
                "organization_access_granted", ctx.user_id, "user", user_id,
                organization_id=organization_id,
            )
        self.session.commit()
        members = self.organization_service.member_reads(ctx, organization_id)
        return next(item for item in members if item.user_id == user_id)

    def revoke_organization_access(self, ctx: AccessContext, organization_id: int, user_id: int) -> None:
        ctx.ensure_admin()
        organization = self.organizations.get_unscoped(organization_id)
        if organization is None:
            raise NotFoundError("Организация не найдена")
        if organization.owner_id == user_id:
            raise ValidationFailedError("Нельзя отозвать доступ владельца")
        if not self.organizations.revoke(organization_id, user_id):
            raise NotFoundError("Доступ не найден")
        self.audit.add(
            "organization_access_revoked", ctx.user_id, "user", user_id,
            organization_id=organization_id,
        )
        self.session.commit()

    def _require_user(self, user_id: int) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError(USER_NOT_FOUND)
        return user

    def _user_read(self, user: User) -> AdminUserRead:
        access_rows = self.organizations.list_access_for_user(user.id)
        org_ids = [row.organization_id for row in access_rows]
        organizations = []
        if org_ids:
            organizations = list(self.session.scalars(
                select(Organization).where(Organization.id.in_(org_ids)).order_by(Organization.name)))
        owner_orgs = list(self.session.scalars(
            select(Organization).where(Organization.owner_id == user.id).order_by(Organization.name)))
        by_id = {item.id: item for item in owner_orgs}
        for item in organizations:
            by_id[item.id] = item
        return AdminUserRead.from_user(user, [OrganizationRead.model_validate(item) for item in by_id.values()])
