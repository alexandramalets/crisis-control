import ipaddress
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models import User, UserSession
from app.schemas.common import ErrorResponse, PageParams
from app.services.access import AccessContext
from app.services.auth_service import AuthService, ClientInfo
from app.services.errors import AuthenticationError

bearer_scheme = HTTPBearer(
    auto_error=False, scheme_name="BearerJWT",
    description="Access-токен из ответа POST /api/v1/auth/login",
)


def get_db() -> Iterator[Session]:
    yield from get_session()


DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_client_info(request: Request) -> ClientInfo:
    host = request.client.host if request.client else None
    try:
        ip_address = str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        ip_address = None
    return ClientInfo(ip_address=ip_address, user_agent=request.headers.get("user-agent"))


Client = Annotated[ClientInfo, Depends(get_client_info)]


@dataclass(frozen=True)
class Principal:
    user: User
    session: UserSession
    access: AccessContext


def get_principal(
    db: DbSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Principal:
    if credentials is None:
        raise AuthenticationError()
    user_session = AuthService(db, settings).authenticate(credentials.credentials)
    user = user_session.user
    return Principal(user=user, session=user_session,
                     access=AccessContext(user_id=user.id, role=user.role.code, session_id=user_session.id))


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def get_access(principal: CurrentPrincipal) -> AccessContext:
    return principal.access


Access = Annotated[AccessContext, Depends(get_access)]


def page_params(limit: Annotated[int, Query(ge=1, le=200)] = 50,
                offset: Annotated[int, Query(ge=0)] = 0) -> PageParams:
    return PageParams(limit=limit, offset=offset)


Pagination = Annotated[PageParams, Depends(page_params)]


def error_responses(*codes: int) -> dict:
    descriptions = {
        401: "Не передан, недействителен или истёк токен доступа",
        403: "Недостаточно прав",
        404: "Объект не найден или недоступен пользователю",
        409: "Конфликт с текущим состоянием данных",
        413: "Файл слишком большой",
        422: "Ошибка проверки данных",
        429: "Временная блокировка после неудачных попыток входа",
        502: "Аналитический сервис вернул некорректный ответ",
        503: "Аналитический сервис или база данных временно недоступны",
    }
    return {code: {"model": ErrorResponse, "description": descriptions[code]} for code in codes}


PROTECTED = error_responses(401)
