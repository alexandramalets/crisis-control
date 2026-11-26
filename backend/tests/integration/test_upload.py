import io

from openpyxl import Workbook

from tests.integration.helpers import auth, create_organization, login

CSV = (
    "period,revenue,profit,cash\n"
    "2024-01,1000.50,100,50\n"
    "2024-02,1100.00,,55\n"
    "2024-03,1200.25,130,60\n"
)


def _xlsx(rows):
    workbook = Workbook()
    sheet = workbook.active
    for row in rows:
        sheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _preview(client, token, filename, content, content_type="text/csv"):
    return client.post("/api/v1/datasets/preview", headers=auth(token),
                       files={"file": (filename, content, content_type)})


def test_upload_csv_preview_validate_import_schema_quality(client, alice):
    token = login(client, "alice")
    organization_id = create_organization(client, token)

    preview = _preview(client, token, "finance.csv", CSV.encode())
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["suggested_period_column"] == "period"
    assert {i["code"] for i in body["suggested_indicators"]} >= {"revenue", "profit", "cash"}
    assert body["preview"][0]["revenue"] == "1000.50"
    staging_id = body["staging_id"]

    quality = client.post("/api/v1/datasets/preview/validate", headers=auth(token), json={
        "staging_id": staging_id, "period_column": "period",
        "indicator_columns": ["revenue", "profit", "cash"],
    })
    assert quality.status_code == 200
    report = quality.json()
    assert report["ready_for_analysis"] is True
    assert report["missing_count"] == 1
    assert report["time_analysis"]["possible"] is True

    imported = client.post(f"/api/v1/organizations/{organization_id}/datasets/import", headers=auth(token), json={
        "staging_id": staging_id, "name": "Финансы 2024", "period_column": "period",
        "indicator_columns": ["revenue", "profit"],
    })
    assert imported.status_code == 201, imported.text
    detail = imported.json()
    assert detail["source_filename"] == "finance.csv"
    assert {i["code"] for i in detail["indicators"]} == {"revenue", "profit"}
    assert next(i for i in detail["indicators"] if i["code"] == "profit")["missing_count"] == 1
    assert any(i["code"] == "missing_values" for i in detail["issues"])

    schema = client.get(f"/api/v1/datasets/{detail['id']}/schema", headers=auth(token))
    assert schema.status_code == 200
    assert schema.json()["period"]["usable_for_time_analysis"] is True

    stored_quality = client.get(f"/api/v1/datasets/{detail['id']}/quality", headers=auth(token))
    assert stored_quality.json()["ready_for_analysis"] is True

    listing = client.get("/api/v1/datasets", headers=auth(token))
    assert listing.json()["total"] >= 1


def test_upload_xlsx_russian_headers(client, alice):
    token = login(client, "alice")
    organization_id = create_organization(client, token)
    content = _xlsx([
        ["период", "Выручка", "Запасы"],
        ["2024-01", 10, 5],
        ["2024-02", 20, 6],
        ["2024-03", 30, 7],
    ])
    preview = _preview(client, token, "ops.xlsx", content,
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert preview.status_code == 200, preview.text
    codes = {i["code"] for i in preview.json()["suggested_indicators"]}
    assert codes == {"revenue", "inventory"}

    imported = client.post(f"/api/v1/organizations/{organization_id}/datasets/import", headers=auth(token), json={
        "staging_id": preview.json()["staging_id"], "name": "Операции",
    })
    assert imported.status_code == 201, imported.text
    assert imported.json()["values_count"] == 6


def test_upload_rejects_empty_unsupported_invalid_and_duplicates(client, alice):
    token = login(client, "alice")
    organization_id = create_organization(client, token)

    empty = _preview(client, token, "empty.csv", b"")
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] in {"empty_file", "validation_error"}

    header_only = _preview(client, token, "empty.csv", b"period,revenue\n")
    assert header_only.status_code == 422

    pdf = _preview(client, token, "notes.pdf", b"%PDF-1.7 fake")
    assert pdf.status_code == 422
    assert "Неподдерживаемый" in pdf.json()["error"]["message"]

    bad_numbers = _preview(client, token, "bad.csv",
                           b"period,revenue\n2024-01,100\n2024-02,xyz\n2024-03,120\n")
    assert bad_numbers.status_code == 200
    check = client.post("/api/v1/datasets/preview/validate", headers=auth(token), json={
        "staging_id": bad_numbers.json()["staging_id"], "period_column": "period",
    })
    assert check.json()["ready_for_analysis"] is False
    assert check.json()["invalid_number_count"] >= 1
    blocked = client.post(f"/api/v1/organizations/{organization_id}/datasets/import", headers=auth(token), json={
        "staging_id": bad_numbers.json()["staging_id"], "name": "Не должен сохраниться",
    })
    assert blocked.status_code == 422

    dupes = _preview(client, token, "dup.csv",
                     b"period,revenue\n2024-01,1\n2024-01,2\n2024-02,3\n")
    check_dupes = client.post("/api/v1/datasets/preview/validate", headers=auth(token), json={
        "staging_id": dupes.json()["staging_id"],
    })
    assert check_dupes.json()["duplicate_count"] >= 1
    assert check_dupes.json()["ready_for_analysis"] is False

    bad_period = _preview(client, token, "dates.csv",
                          b"period,revenue\n2024-01-15,1\n2024-02,2\n2024-03,3\n")
    check_period = client.post("/api/v1/datasets/preview/validate", headers=auth(token), json={
        "staging_id": bad_period.json()["staging_id"],
    })
    assert check_period.json()["invalid_period_count"] >= 1


def test_template_and_path_traversal_name(client, alice):
    token = login(client, "alice")
    csv_tpl = client.get("/api/v1/datasets/template", headers=auth(token), params={"format": "csv"})
    assert csv_tpl.status_code == 200
    assert csv_tpl.content.startswith(b"\xef\xbb\xbfperiod,") or csv_tpl.text.startswith("period,")
    assert b"revenue" in csv_tpl.content

    xlsx_tpl = client.get("/api/v1/datasets/template", headers=auth(token), params={"format": "xlsx"})
    assert xlsx_tpl.status_code == 200
    assert xlsx_tpl.content[:2] == b"PK"

    preview = _preview(client, token, "../../evil.csv", CSV.encode())
    assert preview.status_code == 200
    assert preview.json()["original_filename"] == "evil.csv"


def test_foreign_user_cannot_import_or_read_schema(client, alice, bob):
    owner = login(client, "alice")
    other = login(client, "bob")
    organization_id = create_organization(client, owner)
    preview = _preview(client, owner, "a.csv", CSV.encode())
    staging_id = preview.json()["staging_id"]

    stolen = client.post(f"/api/v1/organizations/{organization_id}/datasets/import", headers=auth(other), json={
        "staging_id": staging_id, "name": "Чужой",
    })
    assert stolen.status_code in {403, 404}

    imported = client.post(f"/api/v1/organizations/{organization_id}/datasets/import", headers=auth(owner), json={
        "staging_id": staging_id, "name": "Свой",
    })
    assert imported.status_code == 201
    dataset_id = imported.json()["id"]
    assert client.get(f"/api/v1/datasets/{dataset_id}/schema", headers=auth(other)).status_code == 404
    assert client.get(f"/api/v1/datasets/{dataset_id}/quality", headers=auth(other)).status_code == 404
