"""Разграничение доступа: чужие объекты не раскрываются (404), администратор только читает."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models import AnalysisProcedure, AnalysisRun, AnalysisRunIndicator, Indicator, Period, Report
from app.models.enums import AnalysisStatus, ProcedureType, ReportFormat, ReportStatus
from tests.integration.helpers import auth, create_dataset, create_organization, dataset_payload, login


@pytest.fixture
def alice_data(client, db, alice):
    """Организация, набор данных, исследование и отчёты пользователя alice."""
    token = login(client, "alice")
    organization_id = create_organization(client, token)
    dataset = create_dataset(client, token, organization_id)

    periods = db.scalars(select(Period).where(Period.granularity == "month").order_by(Period.start_date)).all()
    revenue = db.scalar(select(Indicator).where(Indicator.code == "revenue", Indicator.owner_id.is_(None)))
    run = AnalysisRun(dataset_id=dataset["id"], created_by=alice.id, period_from_id=periods[0].id,
                      period_to_id=periods[-1].id, status=AnalysisStatus.QUEUED, random_state=42)
    db.add(run)
    db.flush()
    db.add(AnalysisRunIndicator(run_id=run.id, indicator_id=revenue.id, weight=1))
    db.add(AnalysisProcedure(run_id=run.id, procedure_type=ProcedureType.ANOMALIES, method="robust_z"))
    ready = Report(run_id=run.id, created_by=alice.id, title="Отчёт", format=ReportFormat.PDF,
                   status=ReportStatus.READY, generated_at=datetime.now(UTC), content=b"%PDF-1.7 test")
    pending = Report(run_id=run.id, created_by=alice.id, title="В работе", format=ReportFormat.XLSX)
    db.add_all([ready, pending])
    db.commit()
    return {"token": token, "organization_id": organization_id, "dataset_id": dataset["id"],
            "run_id": run.id, "report_id": ready.id, "pending_report_id": pending.id}


@pytest.fixture
def bob_token(client, bob):
    return login(client, "bob")


def test_owner_sees_own_resources(client, alice_data):
    headers = auth(alice_data["token"])

    assert client.get(f"/api/v1/datasets/{alice_data['dataset_id']}", headers=headers).status_code == 200
    assert client.get("/api/v1/datasets", headers=headers).json()["total"] == 1

    analysis = client.get(f"/api/v1/analyses/{alice_data['run_id']}", headers=headers)
    assert analysis.status_code == 200
    assert analysis.json()["procedures"][0]["method"] == "robust_z"
    assert analysis.json()["indicators"][0]["code"] == "revenue"
    assert client.get("/api/v1/analyses", headers=headers).json()["total"] == 1

    reports = client.get("/api/v1/reports", headers=headers, params={"run_id": alice_data["run_id"]})
    assert reports.json()["total"] == 2
    content = client.get(f"/api/v1/reports/{alice_data['report_id']}/content", headers=headers)
    assert content.status_code == 200
    assert content.headers["content-type"] == "application/pdf"
    assert content.content == b"%PDF-1.7 test"


def test_pending_report_content_is_conflict(client, alice_data):
    response = client.get(f"/api/v1/reports/{alice_data['pending_report_id']}/content",
                          headers=auth(alice_data["token"]))
    assert response.status_code == 409


@pytest.mark.parametrize("path", [
    "/api/v1/organizations/{organization_id}",
    "/api/v1/organizations/{organization_id}/datasets",
    "/api/v1/datasets/{dataset_id}",
    "/api/v1/datasets/{dataset_id}/values",
    "/api/v1/datasets?organization_id={organization_id}",
    "/api/v1/analyses/{run_id}",
    "/api/v1/analyses?dataset_id={dataset_id}",
    "/api/v1/reports/{report_id}",
    "/api/v1/reports/{report_id}/content",
    "/api/v1/reports?run_id={run_id}",
])
def test_foreign_resources_are_not_found(client, alice_data, bob_token, path):
    response = client.get(path.format(**alice_data), headers=auth(bob_token))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_foreign_resources_are_absent_from_lists(client, alice_data, bob_token):
    for path in ("/api/v1/organizations", "/api/v1/datasets", "/api/v1/analyses", "/api/v1/reports"):
        body = client.get(path, headers=auth(bob_token)).json()
        assert body["total"] == 0 and body["items"] == [], path


def test_foreign_resources_cannot_be_modified(client, alice_data, bob_token):
    headers = auth(bob_token)

    assert client.delete(f"/api/v1/datasets/{alice_data['dataset_id']}", headers=headers).status_code == 404
    assert client.patch(f"/api/v1/organizations/{alice_data['organization_id']}", json={"name": "Захват"},
                        headers=headers).status_code == 404
    assert client.delete(f"/api/v1/organizations/{alice_data['organization_id']}",
                         headers=headers).status_code == 404
    response = client.post(f"/api/v1/organizations/{alice_data['organization_id']}/datasets",
                           json=dataset_payload("Чужой"), headers=headers)
    assert response.status_code == 404

    assert client.get(f"/api/v1/datasets/{alice_data['dataset_id']}",
                      headers=auth(alice_data["token"])).status_code == 200


def test_admin_cannot_read_analyses_and_manages_accounts(client, alice_data, admin):
    headers = auth(login(client, "root.admin"))

    assert client.get(f"/api/v1/datasets/{alice_data['dataset_id']}", headers=headers).status_code == 403
    assert client.get(f"/api/v1/analyses/{alice_data['run_id']}", headers=headers).status_code == 403
    assert client.get("/api/v1/datasets", headers=headers).status_code == 403
    assert client.get("/api/v1/analyses", headers=headers).status_code == 403
    orgs = client.get("/api/v1/organizations", headers=headers)
    assert orgs.status_code == 200
    assert orgs.json()["total"] >= 1

    response = client.delete(f"/api/v1/datasets/{alice_data['dataset_id']}", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


def test_owner_deletes_dataset_with_its_analyses(client, alice_data):
    headers = auth(alice_data["token"])

    assert client.delete(f"/api/v1/datasets/{alice_data['dataset_id']}", headers=headers).status_code == 204

    assert client.get(f"/api/v1/datasets/{alice_data['dataset_id']}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/analyses/{alice_data['run_id']}", headers=headers).status_code == 404
    assert client.get(f"/api/v1/reports/{alice_data['report_id']}", headers=headers).status_code == 404


@pytest.mark.parametrize("method, path", [
    ("get", "/api/v1/organizations"),
    ("get", "/api/v1/datasets"),
    ("get", "/api/v1/datasets/1"),
    ("delete", "/api/v1/datasets/1"),
    ("post", "/api/v1/organizations/1/datasets"),
    ("post", "/api/v1/datasets/preview"),
    ("get", "/api/v1/datasets/template"),
    ("get", "/api/v1/datasets/1/schema"),
    ("get", "/api/v1/datasets/1/quality"),
    ("get", "/api/v1/analyses"),
    ("get", "/api/v1/analyses/1"),
    ("post", "/api/v1/analyses"),
    ("get", "/api/v1/analyses/methods"),
    ("get", "/api/v1/reports"),
    ("get", "/api/v1/reports/1"),
    ("get", "/api/v1/reference/indicators"),
    ("post", "/api/v1/auth/logout"),
])
def test_protected_endpoints_require_token(client, method, path):
    response = getattr(client, method)(path)
    assert response.status_code == 401
