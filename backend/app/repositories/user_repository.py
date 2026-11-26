import uuid
from datetime import datetime

from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.models import RefreshToken, Role, User, UserSession
from app.repositories.base import paginate


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def get_by_login(self, login: str) -> User | None:
        login = (login or "").strip().lower()
        if not login:
            return None
        return self.session.scalar(
            select(User).where(
                or_(func.lower(User.username) == login, func.lower(User.email) == login)
            ).limit(1)
        )

    def exists(self, username: str, email: str) -> bool:
        username = (username or "").strip().lower()
        email = (email or "").strip().lower()
        query = select(User.id).where(or_(
            func.lower(User.username) == username,
            func.lower(User.email) == email,
        )).limit(1)
        return self.session.scalar(query) is not None

    def get_role(self, code: str) -> Role | None:
        return self.session.scalar(select(Role).where(Role.code == code))

    def add(self, user: User) -> User:
        self.session.add(user)
        self.session.flush()
        return user

    def search(self, query: str | None, limit: int, offset: int) -> tuple[list[User], int]:
        stmt = select(User)
        if query:
            pattern = f"%{query.strip().lower()}%"
            stmt = stmt.where(or_(
                User.username.ilike(pattern),
                User.email.ilike(pattern),
                User.full_name.ilike(pattern),
            ))
        return paginate(self.session, stmt.order_by(User.username, User.id), limit, offset)

    def count(self, *, active_only: bool = False) -> int:
        stmt = select(func.count()).select_from(User)
        if active_only:
            stmt = stmt.where(User.is_active.is_(True))
        return self.session.scalar(stmt) or 0


class SessionRepository:
    def __init__(self, session: Session):
        self.session = session

    def add(self, user_session: UserSession) -> UserSession:
        self.session.add(user_session)
        self.session.flush()
        return user_session

    def get(self, session_id: uuid.UUID) -> UserSession | None:
        return self.session.get(UserSession, session_id)

    def revoke_all_for_user(self, user_id: int, now: datetime, except_id: uuid.UUID | None = None) -> None:
        query = update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        if except_id is not None:
            query = query.where(UserSession.id != except_id)
        self.session.execute(query.values(revoked_at=now))

    def add_refresh_token(self, token: RefreshToken) -> RefreshToken:
        self.session.add(token)
        self.session.flush()
        return token

    def get_refresh_token(self, token_hash: str, for_update: bool = False) -> RefreshToken | None:
        query = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        if for_update:
            query = query.with_for_update(of=RefreshToken)
        return self.session.scalar(query)
