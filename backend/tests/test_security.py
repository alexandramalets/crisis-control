import logging
import ssl
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

from app.core.config import Settings, get_settings
from app.core.logging import RedactSecretsFilter, redact
from app.core.security import (
    TokenError, create_access_token, decode_access_token, hash_password, hash_refresh_token, verify_password,
)
from app.core.tls import TLSConfigError, deployment_problems, uvicorn_ssl_kwargs
from app.db.session import describe_connection_error


def test_password_hash_is_argon2id_and_salted():
    first, second = hash_password("Secret-Pass-1"), hash_password("Secret-Pass-1")

    assert first.startswith("$argon2id$")
    assert first != second
    assert verify_password(first, "Secret-Pass-1")
    assert not verify_password(first, "secret-pass-1")
    assert not verify_password(None, "Secret-Pass-1")
    assert not verify_password("not-a-hash", "Secret-Pass-1")


def test_access_token_round_trip():
    session_id = uuid.uuid4()
    token = create_access_token(get_settings(), 7, session_id)

    claims = decode_access_token(get_settings(), token)

    assert claims.user_id == 7 and claims.session_id == session_id


def test_expired_access_token():
    token = create_access_token(get_settings(), 7, uuid.uuid4(), now=datetime.now(UTC) - timedelta(minutes=16))
    with pytest.raises(TokenError) as error:
        decode_access_token(get_settings(), token)
    assert error.value.code == "token_expired"


def test_token_with_wrong_audience(monkeypatch):
    token = create_access_token(get_settings(), 7, uuid.uuid4())
    monkeypatch.setenv("JWT_AUDIENCE", "another-api")
    get_settings.cache_clear()
    with pytest.raises(TokenError) as error:
        decode_access_token(get_settings(), token)
    assert error.value.code == "invalid_token"


def test_refresh_token_hash():
    assert len(hash_refresh_token("abc")) == 64


@pytest.mark.parametrize("message", [
    "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.c2lnbmF0dXJl",
    'body {"password": "hunter2-secret"}',
    "refresh_token=abcDEF123",
])
def test_secrets_are_redacted(message):
    redacted = redact(message)
    assert "hunter2-secret" not in redacted
    assert "eyJzdWIiOiIxIn0" not in redacted
    assert "abcDEF123" not in redacted


def test_log_filter_redacts_record():
    record = logging.LogRecord("x", logging.INFO, __file__, 1, "token=%s", ("abcdef",), None)
    RedactSecretsFilter().filter(record)
    assert record.getMessage() == "token=***"


def test_connection_error_redacts_password():
    exc = OperationalError("SELECT 1", {}, Exception("password=hunter2 host=db"))
    assert "hunter2" not in describe_connection_error(exc)


def test_wildcard_cors_is_rejected():
    with pytest.raises(ValidationError):
        Settings(cors_origins="*")


def test_http_startup_has_no_ssl_files():
    assert uvicorn_ssl_kwargs(None, None) == {}


def test_tls_kwargs_require_both_files(tmp_path):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert.write_text("cert")
    key.write_text("key")
    kwargs = uvicorn_ssl_kwargs(cert, key)
    assert kwargs["ssl_certfile"] == str(cert)
    assert kwargs["ssl_keyfile"] == str(key)
    assert kwargs["ssl_version"] == ssl.PROTOCOL_TLS_SERVER
    with pytest.raises(TLSConfigError):
        uvicorn_ssl_kwargs(cert, None)


def test_require_tls_reports_incomplete_deployment(monkeypatch):
    monkeypatch.setenv("REQUIRE_TLS", "true")
    monkeypatch.setenv("DB_SSLMODE", "prefer")
    monkeypatch.setenv("ANALYTICS_SERVICE_URL", "http://analytics.invalid:8001")
    get_settings.cache_clear()
    text = " ".join(deployment_problems(get_settings()))
    assert "TLS_CERT_FILE" in text
    assert "DB_SSLMODE" in text
    assert "https://" in text


def test_database_url_can_carry_root_certificate(monkeypatch, tmp_path):
    certificate = tmp_path / "ca.crt"
    certificate.write_text("ca")
    monkeypatch.setenv("DB_SSLROOTCERT", str(certificate))
    monkeypatch.setenv("DB_SSLMODE", "verify-full")
    get_settings.cache_clear()
    query = get_settings().database_url.query
    assert query["sslmode"] == "verify-full"
    assert query["sslrootcert"] == str(certificate)
