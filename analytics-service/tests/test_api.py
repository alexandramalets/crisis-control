from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import SERVICE_KEY
from tests.helpers import payload

HEADERS = {"X-Service-Key": SERVICE_KEY}


def client():
    return TestClient(create_app())


def test_anomalies_endpoint_requires_key():
    body = payload(
        [f"2020-{m:02d}" for m in range(1, 9)],
        {"X": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 100.0]},
    ).model_dump()
    http = client()
    assert http.post("/analytics/v1/anomalies", json=body).status_code == 401
    response = http.post("/analytics/v1/anomalies", json=body, headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["result"]["anomalies"][0]["period"] == "2020-08"


def test_invalid_lengths_return_422():
    http = client()
    body = {
        "periods": ["2020", "2021"],
        "indicators": [{"code": "A", "values": [1.0]}],
    }
    response = http.post("/analytics/v1/validate", json=body, headers=HEADERS)
    assert response.status_code == 422
    assert response.json()["error"]["code"] in {"invalid_data", "validation_error"}


def test_analyze_pipeline_runs_selected_procedures():
    body = payload(
        [f"2020-{m:02d}" for m in range(1, 9)],
        {
            "Profit": [10, 11, 12, 13, 14, 15, 16, 17],
            "Debt": [20, 19, 18, 17, 16, 15, 14, 13],
        },
        directions={"Profit": "higher_better", "Debt": "lower_better"},
        bounds={"Profit": (0, 100), "Debt": (0, 100)},
    ).model_dump()
    body["procedures"] = [
        "validate", "anomalies", "trends", "correlation", "clustering", "forecast", "assessment",
    ]
    body["forecast"] = {"horizon": 2}
    body["clustering"] = {"k": 2}
    response = client().post("/analytics/v1/analyze", json=body, headers=HEADERS)
    assert response.status_code == 200
    procedures = response.json()["procedures"]
    assert set(procedures) == {
        "validate", "anomalies", "trends", "correlation", "clustering", "forecast", "assessment",
    }
    trend_flags = [item["significant"] for item in procedures["trends"]["result"]["items"]]
    assert trend_flags and all(flag is True or flag is False for flag in trend_flags)
    for name, item in procedures.items():
        assert item["status"] in {"ok", "skipped", "error"}, name
        assert item["status"] != "error", name


def test_health_open_and_docs_available():
    http = client()
    assert http.get("/analytics/v1/health").status_code == 200
    assert http.get("/analytics/docs").status_code == 200
    assert http.get("/analytics/openapi.json").status_code == 200
