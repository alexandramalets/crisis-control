from decimal import Decimal

import pytest

from tests.integration.helpers import auth, create_dataset, create_organization, dataset_payload, login


@pytest.fixture
def owner(client, alice):
    token = login(client, "alice")
    return token, create_organization(client, token)


def test_create_and_read_dataset(client, owner):
    token, organization_id = owner

    detail = create_dataset(client, token, organization_id)

    assert detail["values_count"] == 6 and detail["periods_count"] == 3
    assert detail["period_from"] == "2024-01-01" and detail["period_to"] == "2024-03-01"
    profit = next(i for i in detail["indicators"] if i["code"] == "profit")
    assert profit["missing_count"] == 1
    assert detail["issues"][0]["code"] == "missing_values"
    assert len(detail["source_sha256"]) == 64

    values = client.get(f"/api/v1/datasets/{detail['id']}/values", headers=auth(token),
                        params={"indicators": "revenue", "from": "2024-02-01"}).json()
    assert values["total"] == 2
    assert Decimal(values["items"][0]["value"]) == Decimal("2000.50")


def test_list_datasets_with_pagination(client, owner):
    token, organization_id = owner
    for number in range(3):
        create_dataset(client, token, organization_id, name=f"Набор {number}")

    page = client.get("/api/v1/datasets", headers=auth(token), params={"limit": 2, "offset": 0}).json()

    assert page["total"] == 3 and len(page["items"]) == 2
    assert page["items"][0]["name"] == "Набор 2"


def test_duplicate_dataset_name_is_conflict(client, owner):
    token, organization_id = owner
    create_dataset(client, token, organization_id)

    response = client.post(f"/api/v1/organizations/{organization_id}/datasets", json=dataset_payload(),
                           headers=auth(token))

    assert response.status_code == 201
    assert response.json()["version_no"] >= 2


def test_unknown_indicator_is_rejected(client, owner):
    token, organization_id = owner
    payload = dataset_payload()
    payload["values"][0]["indicator_code"] = "unknown_metric"

    response = client.post(f"/api/v1/organizations/{organization_id}/datasets", json=payload, headers=auth(token))

    assert response.status_code == 422
    assert response.json()["error"]["details"] == {"unknown_indicators": ["unknown_metric"]}


@pytest.mark.parametrize("mutate", [
    lambda p: p["values"][0].update(period_start="2024-01-15"),
    lambda p: p["values"][0].update(value="1e30"),
    lambda p: p["values"][0].update(value="12.123456"),
    lambda p: p["values"].append(dict(p["values"][0])),
    lambda p: p.update(granularity="quarter"),
    lambda p: p.update(values=[]),
    lambda p: p.update(name=" "),
])
def test_invalid_dataset_payload(client, owner, mutate):
    token, organization_id = owner
    payload = dataset_payload()
    mutate(payload)

    response = client.post(f"/api/v1/organizations/{organization_id}/datasets", json=payload, headers=auth(token))

    assert response.status_code == 422


def test_indicators_reference(client, alice):
    indicators = client.get("/api/v1/reference/indicators", headers=auth(login(client, "alice"))).json()

    assert len(indicators) == 35
    revenue = next(i for i in indicators if i["code"] == "revenue")
    assert revenue["is_system"] and revenue["unit"]["code"] == "RUB"
    assert revenue["impact_direction"] == "higher_better"
