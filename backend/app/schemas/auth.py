from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    AfterValidator, BaseModel, EmailStr, Field, StringConstraints, field_validator, model_validator,
)

from app.schemas.common import ORMModel

USERNAME_PATTERN = r"^[a-z0-9][a-z0-9._-]{2,49}$"
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def _lower_email(value: str) -> str:
    return value.lower()


Username = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, pattern=USERNAME_PATTERN)]
Email = Annotated[EmailStr, Field(max_length=254), AfterValidator(_lower_email)]
Password = Annotated[str, Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH)]
FullName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


def validate_password_policy(password: str, username: str, email: str) -> None:
    lowered = password.lower()
    if lowered in (username, email, email.split("@")[0]):
        raise ValueError("Пароль не должен совпадать с логином или адресом электронной почты")


class LoginRequest(BaseModel):
    login: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=254)] = Field(
        description="Логин или адрес электронной почты",
    )
    password: Annotated[str, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)]


class RegisterRequest(BaseModel):
    username: Username
    email: Email
    full_name: FullName
    password: Password

    @model_validator(mode="after")
    def check_password(self):
        validate_password_policy(self.password, self.username, self.email)
        return self


class ChangePasswordRequest(BaseModel):
    current_password: Annotated[str, Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)]
    new_password: Password


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Срок действия access-токена, секунд")


class UserProfile(ORMModel):
    id: int
    username: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None

    @field_validator("role", mode="before")
    @classmethod
    def role_code(cls, value):
        return getattr(value, "code", value)
