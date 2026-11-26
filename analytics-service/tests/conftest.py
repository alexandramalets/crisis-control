import pytest

SERVICE_KEY = "k" * 32


@pytest.fixture(autouse=True)
def test_settings(monkeypatch):
    monkeypatch.setenv("ANALYTICS_SERVICE_KEY", SERVICE_KEY)
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
