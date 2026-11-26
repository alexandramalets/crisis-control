import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import SERVICE_KEY


@pytest.fixture
def client():
    return TestClient(create_app())


def test_health_reports_library_versions(client):
    response = client.get("/analytics/v1/health")
    assert response.status_code == 200
    libraries = response.json()["libraries"]
    assert set(libraries) == {"pandas", "numpy", "scipy", "scikit-learn", "statsmodels"}


def test_capabilities_requires_service_key(client):
    assert client.get("/analytics/v1/capabilities").status_code == 401
    assert client.get("/analytics/v1/capabilities", headers={"X-Service-Key": "wrong"}).status_code == 401


def test_capabilities_with_service_key(client):
    response = client.get("/analytics/v1/capabilities", headers={"X-Service-Key": SERVICE_KEY})
    assert response.status_code == 200
    types = [item["type"] for item in response.json()["procedures"]]
    assert types == [
        "validate", "anomalies", "trends", "ratios", "correlation", "clustering", "forecast",
        "assessment", "analyze",
    ]
