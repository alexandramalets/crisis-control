import logging
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import create_access_token
from tests.integration.helpers import PASSWORD, auth, login

ME = "/api/v1/auth/me"


def test_login_by_username_returns_token_and_refresh_cookie(client, alice):
    response = client.post("/api/v1/auth/login", json={"login": "alice", "password": PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["expires_in"] == 15 * 60
    assert response.headers["cache-control"] == "no-store"
    cookie = response.headers["set-cookie"]
    assert "refresh_token=" in cookie and "HttpOnly" in cookie and "SameSite=strict" in cookie
    assert "Path=/api/v1/auth" in cookie


def test_login_by_email_is_case_insensitive(client, alice):
    token = login(client, "ALICE@example.org")
    assert client.get(ME, headers=auth(token)).json()["username"] == "alice"


@pytest.mark.parametrize("login_name, password", [("alice", "wrong-password"), ("nobody", PASSWORD)])
def test_wrong_credentials_give_same_error(client, alice, login_name, password):
    response = client.post("/api/v1/auth/login", json={"login": login_name, "password": password})

    assert response.status_code == 401
    assert response.json()["error"] == {"code": "invalid_credentials", "message": "Неверный логин или пароль",
                                        "details": None}


def test_profile_of_current_user(client, alice):
    response = client.get(ME, headers=auth(login(client, "alice")))

    assert response.status_code == 200
    profile = response.json()
    assert profile["username"] == "alice" and profile["role"] == "analyst"
    assert profile["last_login_at"] is not None
    assert "password_hash" not in profile and "password" not in str(profile)


def test_request_without_token_is_rejected(client):
    response = client.get(ME)

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "not_authenticated"


@pytest.mark.parametrize("header", ["Bearer not-a-jwt", "Bearer a.b.c", "Basic YWxpY2U6cGFzcw=="])
def test_malformed_token_is_rejected(client, header):
    response = client.get(ME, headers={"Authorization": header})
    assert response.status_code == 401


def test_expired_token_is_rejected(client, alice, db):
    login(client, "alice")
    from app.models import UserSession

    user_session = db.query(UserSession).filter_by(user_id=alice.id).one()
    expired = create_access_token(get_settings(), alice.id, user_session.id,
                                  now=datetime.now(UTC) - timedelta(hours=1))

    response = client.get(ME, headers=auth(expired))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "token_expired"


def test_token_signed_with_other_key_is_rejected(client, alice):
    token = login(client, "alice")
    payload = jwt.decode(token, options={"verify_signature": False})
    forged = jwt.encode(payload, "x" * 48, algorithm="HS256")

    response = client.get(ME, headers=auth(forged))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_token_with_none_algorithm_is_rejected(client, alice):
    payload = jwt.decode(login(client, "alice"), options={"verify_signature": False})
    unsigned = jwt.encode(payload, None, algorithm="none")
    assert client.get(ME, headers=auth(unsigned)).status_code == 401


def test_logout_revokes_access_and_refresh_tokens(client, alice):
    token = login(client, "alice")

    assert client.post("/api/v1/auth/logout", headers=auth(token)).status_code == 204

    response = client.get(ME, headers=auth(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_revoked"
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_logout_affects_only_current_session(client, alice):
    first = login(client, "alice")
    second = login(client, "alice")

    client.post("/api/v1/auth/logout", headers=auth(first))

    assert client.get(ME, headers=auth(second)).status_code == 200


def test_refresh_rotates_token_and_detects_reuse(client, alice):
    login(client, "alice")
    old_refresh = client.cookies.get("refresh_token")

    response = client.post("/api/v1/auth/refresh")
    assert response.status_code == 200
    new_access = response.json()["access_token"]
    assert client.cookies.get("refresh_token") != old_refresh
    assert client.get(ME, headers=auth(new_access)).status_code == 200

    client.cookies.set("refresh_token", old_refresh, path="/api/v1/auth")
    reuse = client.post("/api/v1/auth/refresh")
    assert reuse.status_code == 401
    # Повторное использование отзывает весь сеанс
    assert client.get(ME, headers=auth(new_access)).status_code == 401


def test_account_is_locked_after_repeated_failures(client, alice):
    for _ in range(5):
        client.post("/api/v1/auth/login", json={"login": "alice", "password": "wrong-password"})

    response = client.post("/api/v1/auth/login", json={"login": "alice", "password": PASSWORD})

    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0


def test_inactive_user_cannot_log_in_and_loses_access(client, alice, db):
    token = login(client, "alice")
    alice.is_active = False
    db.commit()

    assert client.get(ME, headers=auth(token)).status_code == 401
    response = client.post("/api/v1/auth/login", json={"login": "alice", "password": PASSWORD})
    assert response.status_code == 403


def test_registration_disabled_by_default(client):
    response = client.post("/api/v1/auth/register", json={
        "username": "carol", "email": "carol@example.org", "full_name": "Carol", "password": "Long-Enough-1"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "registration_disabled"


class TestRegistrationEnabled:
    @pytest.fixture(autouse=True)
    def enable(self, app_env):
        app_env.setenv("ALLOW_REGISTRATION", "true")
        get_settings.cache_clear()

    def payload(self, **overrides):
        return {"username": "carol", "email": "carol@example.org", "full_name": "Carol",
                "password": "Long-Enough-1"} | overrides

    def test_register_and_login(self, client):
        response = client.post("/api/v1/auth/register", json=self.payload(email="Carol@example.org"))

        assert response.status_code == 201
        assert response.json()["email"] == "carol@example.org" and response.json()["role"] == "analyst"
        assert login(client, "carol", "Long-Enough-1")

    @pytest.mark.parametrize("duplicate", [{"email": "other@example.org"}, {"username": "other"}])
    def test_duplicate_registration_is_rejected(self, client, duplicate):
        assert client.post("/api/v1/auth/register", json=self.payload()).status_code == 201

        response = client.post("/api/v1/auth/register", json=self.payload(**duplicate))

        assert response.status_code == 409

    @pytest.mark.parametrize("overrides", [
        {"password": "short"},
        {"password": "carol"},
        {"password": "carol@example.org"},
        {"email": "not-an-email"},
        {"username": "Ca"},
        {"username": "имя"},
        {"full_name": "   "},
    ])
    def test_invalid_registration_data(self, client, overrides):
        response = client.post("/api/v1/auth/register", json=self.payload(**overrides))
        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "validation_error"
        assert all(any("а" <= ch <= "я" for ch in d["message"].lower()) for d in error["details"]), error


def test_change_password_ends_other_sessions(client, alice):
    current = login(client, "alice")
    other = login(client, "alice")

    wrong = client.put("/api/v1/auth/me/password", headers=auth(current),
                       json={"current_password": "wrong", "new_password": "New-Password-2"})
    assert wrong.status_code == 422

    response = client.put("/api/v1/auth/me/password", headers=auth(current),
                          json={"current_password": PASSWORD, "new_password": "New-Password-2"})
    assert response.status_code == 204
    assert client.get(ME, headers=auth(current)).status_code == 200
    assert client.get(ME, headers=auth(other)).status_code == 401
    assert login(client, "alice", "New-Password-2")


def test_logs_contain_no_passwords_or_tokens(client, alice, caplog):
    caplog.set_level(logging.DEBUG)
    client.post("/api/v1/auth/login", json={"login": "alice", "password": "wrong-password-xyz"})
    token = login(client, "alice")
    client.get(ME, headers=auth(token))
    client.post("/api/v1/auth/refresh")

    assert "wrong-password-xyz" not in caplog.text
    assert PASSWORD not in caplog.text
    assert token not in caplog.text
    assert get_settings().jwt_secret_key.get_secret_value() not in caplog.text
