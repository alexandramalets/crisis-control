from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.auth import Email, FullName, Password, Username, validate_password_policy
from app.schemas.common import ORMModel
from app.schemas.organization import OrganizationRead
from app.services.access import ROLE_ANALYST


class AdminUserCreate(BaseModel):
    username: Username
    email: Email
    full_name: FullName
    password: Password
    role: Literal["analyst", "admin"] = ROLE_ANALYST
    is_active: bool = True
    organization_ids: list[int] = Field(default_factory=list)
    organization_access_level: Literal["view", "edit"] = "view"

    @model_validator(mode="after")
    def check_password(self):
        validate_password_policy(self.password, self.username, self.email)
        return self


class AdminUserUpdate(BaseModel):
    full_name: FullName | None = None
    role: Literal["analyst", "admin"] | None = None
    is_active: bool | None = None


class AdminPasswordReset(BaseModel):
    password: Password


class AdminUserRead(ORMModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    locked_until: datetime | None
    created_at: datetime
    last_login_at: datetime | None
    organizations: list[OrganizationRead] = Field(default_factory=list)

    @classmethod
    def from_user(cls, user, organizations: list | None = None):
        return cls(
            id=user.id, username=user.username, email=user.email, full_name=user.full_name,
            role=user.role.code, is_active=user.is_active, locked_until=user.locked_until,
            created_at=user.created_at, last_login_at=user.last_login_at,
            organizations=organizations or [],
        )


class AuditEventRead(ORMModel):
    id: int
    user_id: int | None
    action: str
    object_type: str | None
    object_id: int | None
    created_at: datetime


class AdminOverview(BaseModel):
    users_total: int
    users_active: int
    organizations_total: int
    datasets_total: int
    analyses_total: int
    analyses_completed: int
    recent_events: list[AuditEventRead]


class OrganizationMemberRead(BaseModel):
    user_id: int
    username: str
    email: str | None = None
    full_name: str
    role: str
    granted_at: datetime
    access_level: Literal["view", "edit"] = "view"
    is_owner: bool = False
    is_active: bool = True
