"""Точка входа: python -m app

Перед запуском HTTP-сервера проверяет конфигурацию, свободный порт и доступность БД,
чтобы ошибки запуска выводились понятным сообщением, а не трассировкой.
"""

import logging
import socket
import sys

import uvicorn
from pydantic import ValidationError
from sqlalchemy.exc import OperationalError

EXIT_CONFIG_ERROR = 2
EXIT_DATABASE_UNAVAILABLE = 3
EXIT_PORT_BUSY = 4
EXIT_MIGRATION_FAILED = 6


def _fail(code: int, message: str) -> None:
    print(f"ОШИБКА ЗАПУСКА: {message}", file=sys.stderr)
    sys.exit(code)


def _check_port(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError:
            _fail(EXIT_PORT_BUSY, f"порт {port} на адресе {host} занят. Укажите другой порт в переменной PORT.")


def main() -> None:
    from app.core.config import get_settings
    from app.core.logging import configure_logging

    try:
        settings = get_settings()
    except ValidationError as exc:
        fields = ", ".join(str(e["loc"][0]).upper() for e in exc.errors())
        _fail(EXIT_CONFIG_ERROR, f"некорректная конфигурация, проверьте переменные окружения: {fields}. "
                                 "Образец — в файле .env.example.")

    configure_logging(settings.log_level)
    logger = logging.getLogger("app.startup")

    from app.core.tls import TLSConfigError, deployment_problems, uvicorn_ssl_kwargs

    problems = deployment_problems(settings)
    if problems:
        _fail(EXIT_CONFIG_ERROR, "; ".join(problems))
    try:
        ssl_kwargs = uvicorn_ssl_kwargs(settings.tls_cert_file, settings.tls_key_file)
    except TLSConfigError as exc:
        _fail(EXIT_CONFIG_ERROR, exc.message)

    _check_port(settings.host, settings.port)

    from app.db.session import wait_for_database

    try:
        version = wait_for_database(settings.db_startup_retries, settings.db_startup_retry_delay)
    except OperationalError:
        _fail(EXIT_DATABASE_UNAVAILABLE,
              f"не удалось подключиться к PostgreSQL {settings.db_host}:{settings.db_port}/{settings.db_name}. "
              "Проверьте, что СУБД запущена, и параметры DB_* в конфигурации.")
    logger.info("Подключение к PostgreSQL %s установлено", version)

    if settings.db_migrate_on_startup:
        from sqlalchemy.exc import ProgrammingError

        from app.db.setup import setup_database

        try:
            revision = setup_database()
        except (OperationalError, ProgrammingError) as exc:
            logger.exception("Ошибка миграции")
            _fail(EXIT_MIGRATION_FAILED, f"не удалось применить миграции схемы БД: {exc.orig}")
        logger.info("Схема БД соответствует ревизии %s", revision)

    uvicorn.run("app.main:create_app", factory=True, host=settings.host, port=settings.port,
                log_level=settings.log_level.lower(), proxy_headers=True, **ssl_kwargs)


if __name__ == "__main__":
    main()
