"""Правила доступа к данным (SEC-1, S-05).

Аналитик видит организации, которыми владеет или к которым администратор назначил доступ,
и связанные наборы, исследования и отчёты. Администратор читает данные всех пользователей.
Изменять и удалять чужие объекты аналитик не может. Назначать доступ и управлять учётными
записями может только администратор. Объект вне области чтения не раскрывается (404).
"""

import uuid
from dataclasses import dataclass

from app.services.errors import PermissionDeniedError

ROLE_ANALYST = "analyst"
ROLE_ADMIN = "admin"
ROLES = (ROLE_ANALYST, ROLE_ADMIN)


@dataclass(frozen=True)
class AccessContext:
    user_id: int
    role: str
    session_id: uuid.UUID | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def read_scope(self) -> int | None:
        """Ограничение выборки по пользователю; None — без ограничения (администратор)."""
        return None if self.is_admin else self.user_id

    def ensure_admin(self) -> None:
        if not self.is_admin:
            raise PermissionDeniedError("Действие доступно только администратору системы")

    def ensure_analyst(self) -> None:
        if self.is_admin:
            raise PermissionDeniedError(
                "Аналитические данные организации доступны только её сотрудникам. "
                "Администратор управляет учётными записями и назначениями доступа."
            )

    def ensure_can_modify(self, owner_id: int) -> None:
        if owner_id != self.user_id:
            raise PermissionDeniedError(
                "Недостаточно прав: загрузка данных и запуск анализа доступны "
                "владельцу организации или сотруднику с правом «редактирование»"
            )
