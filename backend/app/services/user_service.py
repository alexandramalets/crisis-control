from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import User
from app.repositories.user_repository import UserRepository
from app.services.access import ROLES
from app.services.errors import ConflictError, ValidationFailedError

DUPLICATE_USER_MESSAGE = "Пользователь с таким логином или адресом электронной почты уже существует"


class UserService:
    def __init__(self, session: Session):
        self.session = session
        self.users = UserRepository(session)

    def create_user(self, username: str, email: str, full_name: str, password: str, role_code: str) -> User:
        """Создаёт пользователя в текущей транзакции; фиксацию выполняет вызывающий код."""
        if role_code not in ROLES:
            raise ValidationFailedError(f"Неизвестная роль: {role_code}")
        role = self.users.get_role(role_code)
        if role is None:
            raise ValidationFailedError(f"Роль {role_code} отсутствует в справочнике. Примените миграции БД")
        if self.users.exists(username, email):
            raise ConflictError(DUPLICATE_USER_MESSAGE)

        user = User(username=username, email=email.lower(), full_name=full_name,
                    password_hash=hash_password(password), role=role)
        try:
            with self.session.begin_nested():
                self.users.add(user)
        except IntegrityError as exc:
            # Одновременная регистрация с теми же данными
            raise ConflictError(DUPLICATE_USER_MESSAGE) from exc
        return user
