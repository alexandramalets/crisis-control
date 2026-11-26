"""Параметры TLS для запуска uvicorn и проверка стенда с REQUIRE_TLS."""

import ssl
from pathlib import Path

from app.core.config import Settings

_VERIFIED_DB_MODES = {"require", "verify-ca", "verify-full"}


class TLSConfigError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def uvicorn_ssl_kwargs(cert_file: Path | None, key_file: Path | None) -> dict:
    """Пустой словарь — HTTP. Если задан один из файлов, второй тоже обязателен."""
    if cert_file is None and key_file is None:
        return {}
    missing = []
    if cert_file is None or not cert_file.is_file():
        missing.append("TLS_CERT_FILE")
    if key_file is None or not key_file.is_file():
        missing.append("TLS_KEY_FILE")
    if missing:
        raise TLSConfigError(
            "для TLS не найдены файлы: " + ", ".join(missing) + ". Сгенерируйте сертификаты стенда "
            "или уберите REQUIRE_TLS и пути к сертификатам."
        )
    return {
        "ssl_certfile": str(cert_file),
        "ssl_keyfile": str(key_file),
        "ssl_version": ssl.PROTOCOL_TLS_SERVER,
    }


def deployment_problems(settings: Settings) -> list[str]:
    """Замечания только при REQUIRE_TLS. Локальный HTTP без этого флага не считается ошибкой."""
    if not settings.require_tls:
        return []
    problems = []
    if settings.tls_cert_file is None or settings.tls_key_file is None:
        problems.append("REQUIRE_TLS=true требует TLS_CERT_FILE и TLS_KEY_FILE")
    elif not settings.tls_cert_file.is_file() or not settings.tls_key_file.is_file():
        problems.append("файлы TLS_CERT_FILE или TLS_KEY_FILE не найдены")
    if settings.tls_ca_file is None or not settings.tls_ca_file.is_file():
        problems.append("REQUIRE_TLS=true требует файл центра сертификации TLS_CA_FILE")
    if settings.db_sslmode not in _VERIFIED_DB_MODES:
        problems.append("REQUIRE_TLS=true требует DB_SSLMODE=require, verify-ca или verify-full")
    if settings.db_sslmode in {"verify-ca", "verify-full"} and (
        settings.db_sslrootcert is None or not settings.db_sslrootcert.is_file()
    ):
        problems.append("для проверки сертификата PostgreSQL задайте существующий DB_SSLROOTCERT")
    if not settings.analytics_service_url.lower().startswith("https://"):
        problems.append("REQUIRE_TLS=true требует ANALYTICS_SERVICE_URL с https://")
    if settings.analytics_tls_ca_file is None or not settings.analytics_tls_ca_file.is_file():
        problems.append("для HTTPS к аналитическому сервису задайте существующий ANALYTICS_TLS_CA_FILE")
    return problems
