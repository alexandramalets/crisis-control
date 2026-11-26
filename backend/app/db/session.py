import logging
import time
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.logging import redact

logger = logging.getLogger(__name__)


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        echo=settings.db_echo,
        connect_args={"connect_timeout": settings.db_connect_timeout, "application_name": "crisis-backend"},
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session


def database_version() -> str:
    with get_engine().connect() as connection:
        return connection.execute(text("SHOW server_version")).scalar_one()


def describe_connection_error(exc: OperationalError) -> str:
    text = str(exc.orig).strip().splitlines()[0] if exc.orig else str(exc)
    return redact(text)


def wait_for_database(retries: int, delay: float) -> str:
    """Ожидает доступности БД при запуске; возвращает версию сервера или пробрасывает последнюю ошибку."""
    for attempt in range(1, retries + 1):
        try:
            return database_version()
        except OperationalError as exc:
            logger.warning("БД недоступна (попытка %d из %d): %s", attempt, retries, describe_connection_error(exc))
            if attempt == retries:
                raise
            time.sleep(delay)
    raise RuntimeError("unreachable")
