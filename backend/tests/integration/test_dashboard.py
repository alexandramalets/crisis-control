from tests.fake_analytics import FakeAnalyticsClient
from tests.integration.helpers import auth, create_dataset, create_organization, login


def test_dashboard_requires_auth(client):
    response = client.get("/api/v1/dashboard")
    assert response.status_code == 401


def test_dashboard_empty_without_datasets(client, alice):
    token = login(client, "alice")
    response = client.get("/api/v1/dashboard", headers=auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body["empty"] is True
    assert "набор" in body["message"].lower()
    assert body["cards"] == []
    assert body["series"] == []
    assert body["assessment"] is None


def test_dashboard_cards_from_dataset_without_analysis(client, alice):
    token = login(client, "alice")
    organization_id = create_organization(client, token)
    dataset = create_dataset(client, token, organization_id, months=8)
    response = client.get("/api/v1/dashboard", headers=auth(token),
                          params={"dataset_id": dataset["id"], "months": 3})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["empty"] is False
    assert body["dataset"]["id"] == dataset["id"]
    assert body["analysis_run_id"] is None
    assert body["assessment"] is None
    codes = [card["code"] for card in body["cards"]]
    assert codes == ["revenue", "profit", "receivables", "payables", "cash"]
    revenue = body["cards"][0]
    assert revenue["name"] == "Выручка"
    assert float(revenue["value"]) == 8000.5
    assert revenue["change_direction"] == "up"
    assert revenue["change_favorable"] is True
    assert len(revenue["sparkline"]) >= 3
    assert body["series"][0]["code"] == "revenue"
    assert all(point["kind"] == "history" for point in body["series"][0]["history"])
    assert body["series"][0]["forecast"] == []
    cash = next(card for card in body["cards"] if card["code"] == "cash")
    assert cash["value"] is None


def test_dashboard_uses_stored_analysis_results(client, alice, monkeypatch):
    fake = FakeAnalyticsClient()
    monkeypatch.setattr("app.services.analysis_service.get_analytics_client", lambda settings=None: fake)
    token = login(client, "alice")
    organization_id = create_organization(client, token)
    dataset = create_dataset(client, token, organization_id, months=8)
    headers = auth(token)
    started = client.post("/api/v1/analyses", json={
        "dataset_id": dataset["id"],
        "indicators": [{"code": "revenue", "weight": 0.5}, {"code": "profit", "weight": 0.5}],
        "forecast": {"horizon": 3},
        "clustering": {"k": 2},
    }, headers=headers)
    assert started.status_code == 200, started.text
    run_id = started.json()["id"]

    response = client.get("/api/v1/dashboard", headers=headers, params={"dataset_id": dataset["id"]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["analysis_run_id"] == run_id
    assert body["assessment"]["score"] is not None
    assert float(body["assessment"]["score"]) == 45
    assert body["assessment"]["interpretation"] == "Повышенный риск"
    assert body["assessment"]["groups"]
    assert body["anomalies"]
    assert body["anomalies"][0]["indicator"] == "revenue"
    assert body["correlations"]["pairs"]
    revenue_series = next(item for item in body["series"] if item["code"] == "revenue")
    assert revenue_series["forecast"]
    assert all(point["kind"] == "forecast" for point in revenue_series["forecast"])
    assert body["recent_runs"][0]["id"] == run_id
