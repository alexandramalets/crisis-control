from datetime import date

from fastapi.testclient import TestClient

PASSWORD = "Integration-Test-Pass-1"


def login(client: TestClient, login_name: str, password: str = PASSWORD) -> str:
    response = client.post("/api/v1/auth/login", json={"login": login_name, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def create_organization(client: TestClient, token: str, name: str = "ООО «Пример»") -> int:
    response = client.post("/api/v1/organizations", json={"name": name}, headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()["id"]


def dataset_payload(name: str = "Синтетический набор", months: int = 3) -> dict:
    values = []
    for month in range(1, months + 1):
        start = date(2024, month, 1).isoformat()
        values.append({"indicator_code": "revenue", "period_start": start, "value": f"{1000 * month}.50"})
        values.append({"indicator_code": "profit", "period_start": start, "value": None if month == 2 else "100"})
    return {"name": name, "granularity": "month", "values": values}


def create_dataset(client: TestClient, token: str, organization_id: int, name: str = "Синтетический набор",
                   months: int = 3) -> dict:
    response = client.post(f"/api/v1/organizations/{organization_id}/datasets",
                           json=dataset_payload(name, months=months), headers=auth(token))
    assert response.status_code == 201, response.text
    return response.json()
