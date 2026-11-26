from decimal import Decimal

from app.integrations.analytics_client import AnalyticsServiceError
from tests.fake_analytics import FakeAnalyticsClient
from tests.integration.helpers import auth, create_dataset, create_organization, login


def _patch_client(monkeypatch, fake: FakeAnalyticsClient):
    monkeypatch.setattr("app.services.analysis_service.get_analytics_client", lambda settings=None: fake)


def _start_body(dataset_id: int) -> dict:
    return {
        "dataset_id": dataset_id,
        "indicators": [{"code": "revenue", "weight": 0.5}, {"code": "profit", "weight": 0.5}],
        "forecast": {"horizon": 3},
        "clustering": {"k": 2},
    }


def test_full_analysis_flow_saves_and_rereads_results(client, db, alice, monkeypatch):
    fake = FakeAnalyticsClient()
    _patch_client(monkeypatch, fake)
    token = login(client, "alice")
    organization_id = create_organization(client, token)
    dataset = create_dataset(client, token, organization_id, months=8)
    headers = auth(token)

    started = client.post("/api/v1/analyses", json=_start_body(dataset["id"]), headers=headers)
    assert started.status_code == 200, started.text
    body = started.json()
    assert body["status"] == "completed"
    assert body["analytics_service_version"] == "0.1.0"
    run_id = body["id"]
    assert {p["procedure_type"] for p in body["procedures"]} >= {
        "preprocessing", "anomalies", "correlation", "clustering", "forecasting", "assessment",
        "trends", "ratios",
    }
    assert all(p["status"] == "ok" for p in body["procedures"])
    assert fake.payloads and fake.payloads[0]["periods"][0] == "2024-01"
    sent = fake.payloads[0]
    assert "ratios" in sent["procedures"] and "trends" in sent["procedures"]
    assert sent["correlation"]["method"] == "pearson"
    assert sent["forecast"]["horizon"] == 3
    assert sent.get("method") is None

    listed = client.get("/api/v1/analyses", headers=headers, params={"dataset_id": dataset["id"]})
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == run_id

    again = client.get(f"/api/v1/analyses/{run_id}", headers=headers)
    assert again.status_code == 200
    assert again.json()["status"] == "completed"

    results = client.get(f"/api/v1/analyses/{run_id}/results", headers=headers)
    assert results.status_code == 200
    payload = results.json()
    assert payload["anomalies"]["items"][0]["direction"] == "above"
    assert payload["anomalies"]["items"][0]["score"] == 5.5
    assert payload["correlation"]["pairs"][0]["coefficient"] == 1.0
    assert "причин" in payload["correlation"]["interpretation"]
    assert payload["clustering"]["clusters"]
    assert "кризис" not in (payload["clustering"]["clusters"][0]["label"] or "").lower() or "не диагноз" in payload["clustering"]["clusters"][0]["label"].lower()
    assert payload["forecast"]["series"][0]["points"]
    assert Decimal(str(payload["assessment"]["score"])) == Decimal("45.00") or Decimal(str(payload["assessment"]["score"])) == Decimal("45")

    anomalies = client.get(f"/api/v1/analyses/{run_id}/anomalies", headers=headers).json()
    assert anomalies["items"][0]["indicator"] == "revenue"
    assessment = client.get(f"/api/v1/analyses/{run_id}/assessment", headers=headers).json()
    assert assessment["status_label"] == "Рассчитано"


def test_single_procedure_endpoint(client, alice, monkeypatch):
    fake = FakeAnalyticsClient()
    _patch_client(monkeypatch, fake)
    token = login(client, "alice")
    organization_id = create_organization(client, token)
    dataset = create_dataset(client, token, organization_id, months=8)

    response = client.post("/api/v1/analyses/anomalies", json={"dataset_id": dataset["id"]}, headers=auth(token))
    assert response.status_code == 200, response.text
    types = [p["procedure_type"] for p in response.json()["procedures"]]
    assert types == ["preprocessing", "anomalies"]
    run_id = response.json()["id"]
    stored = client.get(f"/api/v1/analyses/{run_id}/anomalies", headers=auth(token))
    assert stored.status_code == 200
    assert stored.json()["items"]


def test_unavailable_analytics_does_not_fake_success(client, alice, monkeypatch):
    fake = FakeAnalyticsClient(error=AnalyticsServiceError("Аналитический сервис недоступен. Повторите попытку позже."))
    _patch_client(monkeypatch, fake)
    token = login(client, "alice")
    organization_id = create_organization(client, token)
    dataset = create_dataset(client, token, organization_id, months=8)

    response = client.post("/api/v1/analyses", json=_start_body(dataset["id"]), headers=auth(token))
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "analytics_unavailable"
    assert "недоступен" in error["message"].lower()
    run_id = error["details"]["run_id"]

    stored = client.get(f"/api/v1/analyses/{run_id}", headers=auth(token))
    assert stored.status_code == 200
    assert stored.json()["status"] == "failed"
    assert stored.json()["error_message"]


def test_foreign_dataset_analysis_is_not_found(client, alice, bob, monkeypatch):
    _patch_client(monkeypatch, FakeAnalyticsClient())
    alice_token = login(client, "alice")
    organization_id = create_organization(client, alice_token)
    dataset = create_dataset(client, alice_token, organization_id, months=8)

    bob_token = login(client, "bob")
    response = client.post("/api/v1/analyses", json=_start_body(dataset["id"]), headers=auth(bob_token))
    assert response.status_code == 404


def test_too_few_periods_rejected_before_call(client, alice, monkeypatch):
    fake = FakeAnalyticsClient()
    _patch_client(monkeypatch, fake)
    token = login(client, "alice")
    organization_id = create_organization(client, token)
    dataset = create_dataset(client, token, organization_id, months=2)

    response = client.post("/api/v1/analyses", json={"dataset_id": dataset["id"]}, headers=auth(token))
    assert response.status_code == 422
    assert fake.payloads == []
