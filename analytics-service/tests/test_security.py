import logging

from fastapi.testclient import TestClient

from app.core.logging import RedactFilter
from app.core.tls import deployment_problems, uvicorn_ssl_kwargs
from app.main import create_app
from tests.conftest import SERVICE_KEY


def test_service_key_and_jwt_are_redacted():
    key = "k" * 40
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "X-Service-Key: %s", (key,), None)
    RedactFilter().filter(record)
    assert key not in record.getMessage()
    token = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl"
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "saw %s", (token,), None)
    RedactFilter().filter(record)
    assert "eyJzdWIiOiIxIn0" not in record.getMessage()


def test_unhandled_error_hides_details():
    app = create_app()

    @app.get("/analytics/v1/boom-test")
    def boom():
        raise RuntimeError(f"key={SERVICE_KEY}")

    response = TestClient(app, raise_server_exceptions=False).get("/analytics/v1/boom-test")
    assert response.status_code == 500
    assert response.json()["error"]["message"] == "Внутренняя ошибка сервиса"
    assert SERVICE_KEY not in response.text
    assert "Traceback" not in response.text


def test_tls_disabled_by_default():
    from app.core.config import get_settings

    assert uvicorn_ssl_kwargs(None, None) == {}
    assert deployment_problems(get_settings()) == []


def test_require_tls_without_files(monkeypatch):
    monkeypatch.setenv("REQUIRE_TLS", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()
    assert any("TLS_CERT_FILE" in item for item in deployment_problems(get_settings()))
    assert uvicorn_ssl_kwargs(None, None) == {}
