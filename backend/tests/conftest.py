import pytest

TEST_ENV = {
    "APP_ENV": "test",
    "DB_PASSWORD": "test-password",
    "ANALYTICS_SERVICE_URL": "http://analytics.invalid:8001",
    "ANALYTICS_SERVICE_KEY": "k" * 32,
    "JWT_SECRET_KEY": "s" * 32,
    "DATASET_ENCRYPTION_KEY": "e" * 32,
    "DB_HOST": "db.invalid",
}


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    for name, value in TEST_ENV.items():
        monkeypatch.setenv(name, value)
    from app.core.config import get_settings
    from app.db.session import get_engine, get_session_factory

    from app.integrations.analytics_client import _shared_breaker

    caches = (get_settings, get_engine, get_session_factory, _shared_breaker)
    for cached in caches:
        cached.cache_clear()
    yield
    for cached in caches:
        cached.cache_clear()
