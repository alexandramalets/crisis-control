import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import (
    TokenError, create_access_token, decode_access_token, generate_refresh_token, hash_password,
    hash_refresh_token, password_needs_rehash, verify_password,
)
from app.models import RefreshToken, User, UserSession
from app.repositories.audit_repository import AuditRepository
from app.repositories.user_repository import SessionRepository, UserRepository
from app.schemas.auth import RegisterRequest, validate_password_policy
from app.services.access import ROLE_ANALYST
from app.services.errors import (
    AuthenticationError, PermissionDeniedError, TooManyAttemptsError, ValidationFailedError,
)
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

INVALID_CREDENTIALS = "Неверный логин или пароль"
SESSION_ENDED = "Сеанс завершён. Войдите в систему снова"


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(frozen=True)
class ClientInfo:
    ip_address: str | None = None
    user_agent: str | None = None


class AuthService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings
        self.users = UserRepository(session)
        self.sessions = SessionRepository(session)
        self.audit = AuditRepository(session)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)

    def _issue(self, user_session: UserSession, now: datetime) -> IssuedTokens:
        refresh_token = generate_refresh_token()
        expires_at = now + timedelta(days=self.settings.refresh_token_ttl_days)
        user_session.expires_at = expires_at
        self.sessions.add_refresh_token(RefreshToken(
            session_id=user_session.id, token_hash=hash_refresh_token(refresh_token),
            issued_at=now, expires_at=expires_at,
        ))
        access_token = create_access_token(self.settings, user_session.user_id, user_session.id, now)
        return IssuedTokens(access_token, self.settings.access_token_ttl_minutes * 60, refresh_token, expires_at)

    def login(self, login: str, password: str, client: ClientInfo) -> IssuedTokens:
        now = self._now()
        user = self.users.get_by_login(login)

        if user is not None and user.locked_until is not None and user.locked_until > now:
            retry_after = int((user.locked_until - now).total_seconds()) + 1
            self.audit.add("login_locked", user.id, "user", user.id, client.ip_address)
            self.session.commit()
            raise TooManyAttemptsError(
                "Слишком много неудачных попыток входа. Повторите позже",
                details={"retry_after_seconds": retry_after}, headers={"Retry-After": str(retry_after)},
            )

        if not verify_password(user.password_hash if user else None, password):
            if user is not None:
                user.failed_login_count += 1
                if user.failed_login_count >= self.settings.login_max_failures:
                    user.locked_until = now + timedelta(minutes=self.settings.login_lock_minutes)
                    user.failed_login_count = 0
                    logger.warning("Учётная запись id=%s заблокирована после неудачных попыток входа", user.id)
            self.audit.add("login_failed", user.id if user else None, "user", user.id if user else None,
                           client.ip_address)
            self.session.commit()
            raise AuthenticationError(INVALID_CREDENTIALS, code="invalid_credentials")

        if not user.is_active:
            raise PermissionDeniedError("Учётная запись отключена", code="account_disabled")

        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        if password_needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)

        user_session = self.sessions.add(UserSession(
            user_id=user.id, created_at=now, expires_at=now + timedelta(days=self.settings.refresh_token_ttl_days),
            ip_address=client.ip_address, user_agent=(client.user_agent or "")[:255] or None,
        ))
        tokens = self._issue(user_session, now)
        self.audit.add("login", user.id, "user", user.id, client.ip_address)
        self.session.commit()
        logger.info("Вход пользователя id=%s", user.id)
        return tokens

    def refresh(self, refresh_token: str | None, client: ClientInfo) -> IssuedTokens:
        if not refresh_token:
            raise AuthenticationError("Отсутствует refresh-токен", code="invalid_refresh_token")
        now = self._now()
        token = self.sessions.get_refresh_token(hash_refresh_token(refresh_token), for_update=True)
        if token is None:
            raise AuthenticationError(SESSION_ENDED, code="invalid_refresh_token")

        user_session = token.session
        if user_session.revoked_at is not None or user_session.expires_at <= now or not user_session.user.is_active:
            raise AuthenticationError(SESSION_ENDED, code="session_revoked")
        if token.used_at is not None:
            # Повторное использование уже обменянного токена — признак его кражи
            user_session.revoked_at = now
            self.audit.add("refresh_token_reuse", user_session.user_id, "session", None, client.ip_address)
            self.session.commit()
            logger.warning("Повторное использование refresh-токена, сеанс пользователя id=%s отозван",
                           user_session.user_id)
            raise AuthenticationError(SESSION_ENDED, code="session_revoked")
        if token.expires_at <= now:
            raise AuthenticationError(SESSION_ENDED, code="session_expired")

        token.used_at = now
        tokens = self._issue(user_session, now)
        self.session.commit()
        return tokens

    def authenticate(self, access_token: str) -> UserSession:
        try:
            claims = decode_access_token(self.settings, access_token)
        except TokenError as exc:
            raise AuthenticationError(exc.message, code=exc.code) from exc

        user_session = self.sessions.get(claims.session_id)
        if (user_session is None or user_session.user_id != claims.user_id
                or user_session.revoked_at is not None or user_session.expires_at <= self._now()):
            raise AuthenticationError(SESSION_ENDED, code="session_revoked")
        if not user_session.user.is_active:
            raise AuthenticationError("Учётная запись отключена", code="account_disabled")
        return user_session

    def logout(self, user_session: UserSession, client: ClientInfo) -> None:
        user_session.revoked_at = self._now()
        self.audit.add("logout", user_session.user_id, "user", user_session.user_id, client.ip_address)
        self.session.commit()

    def register(self, data: RegisterRequest, client: ClientInfo) -> User:
        if not self.settings.allow_registration:
            raise PermissionDeniedError("Самостоятельная регистрация отключена. Обратитесь к администратору",
                                        code="registration_disabled")
        user = UserService(self.session).create_user(
            data.username, data.email, data.full_name, data.password, ROLE_ANALYST)
        self.audit.add("register", user.id, "user", user.id, client.ip_address)
        self.session.commit()
        return user

    def change_password(self, user_session: UserSession, current_password: str, new_password: str,
                        client: ClientInfo) -> None:
        user = user_session.user
        if not verify_password(user.password_hash, current_password):
            raise ValidationFailedError("Текущий пароль указан неверно", code="invalid_password")
        try:
            validate_password_policy(new_password, user.username, user.email)
        except ValueError as exc:
            raise ValidationFailedError(str(exc)) from exc
        user.password_hash = hash_password(new_password)
        # Остальные сеансы завершаются: при смене пароля из-за компрометации они могли быть чужими
        self.sessions.revoke_all_for_user(user.id, self._now(), except_id=user_session.id)
        self.audit.add("password_changed", user.id, "user", user.id, client.ip_address)
        self.session.commit()
