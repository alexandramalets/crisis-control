"""Интеграционные тесты на реальной PostgreSQL.

Нужна отдельная тестовая БД (имя оканчивается на _test: тесты пересоздают схему).
Параметры — переменные окружения TEST_DB_HOST, TEST_DB_PORT, TEST_DB_NAME, TEST_DB_USER,
TEST_DB_PASSWORD. Без TEST_DB_PASSWORD или при недоступной СУБД тесты пропускаются.
Каждый тест выполняется в транзакции, которая откатывается после теста.
"""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.db.migrations import downgrade_to_base, upgrade_to_head
from app.services.access import ROLE_ADMIN, ROLE_ANALYST
from app.services.user_service import UserService
from tests.integration.helpers import PASSWORD


def _test_database_url() -> URL:
    password = os.environ.get("TEST_DB_PASSWORD")
    if not password:
        pytest.skip("TEST_DB_PASSWORD не задан — интеграционные тесты пропущены")
    name = os.environ.get("TEST_DB_NAME", "crisis_analytics_test")
    if not name.endswith("_test"):
        pytest.exit(f"Отказ: имя тестовой БД должно оканчиваться на _test (получено {name})", returncode=2)
    return URL.create(
        "postgresql+psycopg",
        username=os.environ.get("TEST_DB_USER", "crisis_app"),
        password=password,
        host=os.environ.get("TEST_DB_HOST", "127.0.0.1"),
        port=int(os.environ.get("TEST_DB_PORT", "5433")),
        database=name,
    )


@pytest.fixture(scope="session")
def engine():
    engine = create_engine(_test_database_url(), connect_args={"connect_timeout": 3})
    try:
        with engine.connect():
            pass
    except OperationalError as exc:
        pytest.skip(f"Тестовая PostgreSQL недоступна: {exc.orig}")
    with engine.begin() as connection:
        downgrade_to_base(connection)
    with engine.begin() as connection:
        upgrade_to_head(connection)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint",
                      autoflush=False, expire_on_commit=False)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def app_env(monkeypatch, tmp_path):
    monkeypatch.setenv("REFRESH_COOKIE_SECURE", "false")
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("DATASET_ENCRYPTION_KEY", "e" * 32)
    from app.core.config import get_settings

    get_settings.cache_clear()
    return monkeypatch


@pytest.fixture
def client(db, app_env):
    from app.main import create_app

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_user(db):
    def factory(username: str, role: str = ROLE_ANALYST, password: str = PASSWORD):
        user = UserService(db).create_user(username, f"{username}@example.org", username.title(), password, role)
        db.commit()
        return user
    return factory


@pytest.fixture
def alice(make_user):
    return make_user("alice")


@pytest.fixture
def bob(make_user):
    return make_user("bob")


@pytest.fixture
def admin(make_user):
    return make_user("root.admin", role=ROLE_ADMIN)
