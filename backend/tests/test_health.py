import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1 import health
from app.integrations.analytics_client import AnalyticsServiceError
from app.main import create_app


@pytest.fixture
def client():
    return TestClient(create_app())


def test_liveness(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_readiness_ok(client, monkeypatch):
    monkeypatch.setattr(health, "database_version", lambda: "18.1")
    monkeypatch.setattr(health, "schema_revisions", lambda: ("0002", "0002"))
    monkeypatch.setattr(health.analytics_client, "get_health", lambda _: {"version": "0.1.0"})
    monkeypatch.setattr(health.analytics_client, "get_capabilities", lambda _: {})

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 200
    database = response.json()["components"]["database"]
    assert database["version"] == "18.1"
    assert database["schema_revision"] == "0002"


def test_readiness_degraded_when_schema_outdated(client, monkeypatch):
    monkeypatch.setattr(health, "database_version", lambda: "18.1")
    monkeypatch.setattr(health, "schema_revisions", lambda: (None, "0002"))
    monkeypatch.setattr(health.analytics_client, "get_health", lambda _: {"version": "0.1.0"})
    monkeypatch.setattr(health.analytics_client, "get_capabilities", lambda _: {})

    response = client.get("/api/v1/health/ready")

    assert response.status_code == 503
    assert response.json()["components"]["database"]["expected_revision"] == "0002"


def test_readiness_degraded_when_dependencies_unavailable(client, monkeypatch):
    def unavailable(_):
        raise AnalyticsServiceError("Аналитический сервис недоступен: ConnectError")

    monkeypatch.setattr(health.analytics_client, "get_health", unavailable)

    response = client.get("/api/v1/health/ready")

    body = response.json()
    assert response.status_code == 503
    assert body["status"] == "degraded"
    assert body["components"]["database"]["status"] == "error"
    assert body["components"]["analytics"]["status"] == "error"


def test_unhandled_error_does_not_leak_exception_text():
    app = create_app()

    @app.get("/api/v1/boom-test")
    def boom():
        raise RuntimeError("password=hunter2-secret")

    response = TestClient(app, raise_server_exceptions=False).get("/api/v1/boom-test")
    assert response.status_code == 500
    assert response.json()["error"] == {
        "code": "internal_error", "message": "Внутренняя ошибка сервера", "details": None,
    }
    assert "hunter2" not in response.text
    assert "Traceback" not in response.text


def test_unknown_route_uses_unified_error_format(client):
    response = client.get("/api/v1/unknown")
    assert response.status_code == 404
    assert response.json()["error"]["message"] == "Ресурс не найден"


def test_short_jwt_secret_is_rejected(monkeypatch):
    from app.core.config import Settings

    monkeypatch.setenv("JWT_SECRET_KEY", "short")
    with pytest.raises(ValidationError):
        Settings()
