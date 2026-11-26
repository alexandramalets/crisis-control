from tests.integration.helpers import auth, create_organization, login


def test_analyst_cannot_use_admin_api(client, alice):
    headers = auth(login(client, "alice"))
    assert client.get("/api/v1/admin/overview", headers=headers).status_code == 403
    assert client.get("/api/v1/admin/users", headers=headers).status_code == 403
    created = client.post("/api/v1/admin/users", headers=headers, json={
        "username": "intruder", "email": "intruder@example.org", "full_name": "Intruder",
        "password": "Long-Enough-1",
    })
    assert created.status_code == 403


def test_admin_overview_uses_real_counts(client, admin, alice):
    headers = auth(login(client, "root.admin"))
    body = client.get("/api/v1/admin/overview", headers=headers).json()
    assert body["users_total"] >= 2
    assert body["users_active"] >= 2
    assert "organizations_total" in body and "datasets_total" in body
    assert "recent_events" in body


def test_admin_creates_user_and_grants_organization(client, admin, alice, bob):
    admin_headers = auth(login(client, "root.admin"))
    alice_token = login(client, "alice")
    organization_id = create_organization(client, alice_token)

    created = client.post("/api/v1/admin/users", headers=admin_headers, json={
        "username": "carol", "email": "carol@example.org", "full_name": "Carol Analyst",
        "password": "Long-Enough-1", "role": "analyst", "organization_ids": [organization_id],
    })
    assert created.status_code == 201, created.text
    carol = created.json()
    assert carol["role"] == "analyst" and carol["is_active"] is True
    assert any(item["id"] == organization_id for item in carol["organizations"])

    carol_headers = auth(login(client, "carol", "Long-Enough-1"))
    visible = client.get("/api/v1/organizations", headers=carol_headers).json()
    assert visible["total"] == 1
    assert visible["items"][0]["id"] == organization_id

    bob_headers = auth(login(client, "bob"))
    assert client.get(f"/api/v1/organizations/{organization_id}", headers=bob_headers).status_code == 404

    granted = client.put(
        f"/api/v1/admin/organizations/{organization_id}/access/{bob.id}", headers=admin_headers)
    assert granted.status_code == 200
    visible = client.get(f"/api/v1/organizations/{organization_id}", headers=bob_headers)
    assert visible.status_code == 200
    assert visible.json()["can_edit"] is False
    assert visible.json()["access_level"] == "view"

    edit = client.put(
        f"/api/v1/admin/organizations/{organization_id}/access/{bob.id}?access_level=edit",
        headers=admin_headers)
    assert edit.status_code == 200
    editable = client.get(f"/api/v1/organizations/{organization_id}", headers=bob_headers)
    assert editable.status_code == 200
    assert editable.json()["can_edit"] is True

    revoked = client.delete(
        f"/api/v1/admin/organizations/{organization_id}/access/{bob.id}", headers=admin_headers)
    assert revoked.status_code == 204
    assert client.get(f"/api/v1/organizations/{organization_id}", headers=bob_headers).status_code == 404


def test_admin_blocks_user_and_resets_password(client, admin, alice):
    admin_headers = auth(login(client, "root.admin"))
    blocked = client.patch(f"/api/v1/admin/users/{alice.id}", headers=admin_headers, json={"is_active": False})
    assert blocked.status_code == 200
    assert blocked.json()["is_active"] is False
    denied = client.post("/api/v1/auth/login", json={"login": "alice", "password": "Integration-Test-Pass-1"})
    assert denied.status_code == 403

    client.patch(f"/api/v1/admin/users/{alice.id}", headers=admin_headers, json={"is_active": True})
    reset = client.post(f"/api/v1/admin/users/{alice.id}/password", headers=admin_headers,
                        json={"password": "New-Password-9"})
    assert reset.status_code == 204
    old = client.post("/api/v1/auth/login", json={"login": "alice", "password": "Integration-Test-Pass-1"})
    assert old.status_code == 401
    fresh = client.post("/api/v1/auth/login", json={"login": "alice", "password": "New-Password-9"})
    assert fresh.status_code == 200


def test_analyst_cannot_grant_organization_access(client, alice, bob):
    alice_headers = auth(login(client, "alice"))
    organization_id = create_organization(client, login(client, "alice"))
    response = client.put(
        f"/api/v1/admin/organizations/{organization_id}/access/{bob.id}", headers=alice_headers)
    assert response.status_code == 403
