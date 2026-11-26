from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints, model_validator

from app.schemas.auth import Email, FullName, Password, Username, validate_password_policy
from app.schemas.common import ORMModel

OrganizationName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]


class OrganizationCreate(BaseModel):
    name: OrganizationName
    description: Description | None = None


class OrganizationUpdate(BaseModel):
    name: OrganizationName | None = None
    description: Description | None = None


class OrganizationRead(ORMModel):
    id: int
    owner_id: int
    name: str
    description: str | None
    created_at: datetime
    access_level: Literal["view", "edit"] = "view"
    can_edit: bool = False


class OrganizationSummary(OrganizationRead):
    members_count: int = 0
    datasets_count: int = 0
    analyses_count: int = 0
    last_analysis_at: datetime | None = None


class OrganizationMemberAssign(BaseModel):
    user_id: int | None = None
    login: str | None = None
    access_level: Literal["view", "edit"] = "view"


class OrganizationEmployeeCreate(BaseModel):
    username: Username
    email: Email
    full_name: FullName
    password: Password
    access_level: Literal["view", "edit"] = "view"

    @model_validator(mode="after")
    def check_password(self):
        validate_password_policy(self.password, self.username, self.email)
        return self
