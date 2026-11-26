"""Создание и обновление схемы БД, начальное заполнение справочников.

Запуск: python -m app.db.setup [--check]
  без параметров — дождаться СУБД и применить все миграции (включая справочники);
  --check        — только сообщить, соответствует ли схема последней миграции.
"""

import argparse
import logging
import sys

from pydantic import ValidationError
from sqlalchemy.exc import OperationalError, ProgrammingError

EXIT_OK = 0
EXIT_CONFIG_ERROR = 2
EXIT_DATABASE_UNAVAILABLE = 3
EXIT_SCHEMA_OUTDATED = 5
EXIT_MIGRATION_FAILED = 6


def setup_database() -> str:
    """Применяет миграции до последней версии; возвращает номер ревизии."""
    from app.db.migrations import current_revision, upgrade_to_head
    from app.db.session import get_engine

    with get_engine().begin() as connection:
        upgrade_to_head(connection)
    with get_engine().connect() as connection:
        return current_revision(connection)


def schema_state() -> tuple[str | None, str]:
    from app.db.migrations import current_revision, head_revision
    from app.db.session import get_engine

    with get_engine().connect() as connection:
        return current_revision(connection), head_revision()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Настройка схемы базы данных")
    parser.add_argument("--check", action="store_true", help="только проверить версию схемы")
    args = parser.parse_args(argv)

    from app.core.config import get_settings
    from app.core.logging import configure_logging

    try:
        settings = get_settings()
    except ValidationError as exc:
        fields = ", ".join(str(e["loc"][0]).upper() for e in exc.errors())
        print(f"ОШИБКА: некорректная конфигурация: {fields}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    configure_logging(settings.log_level)

    from app.db.session import describe_connection_error, wait_for_database

    try:
        wait_for_database(settings.db_startup_retries, settings.db_startup_retry_delay)
        if args.check:
            current, head = schema_state()
            print(f"Текущая ревизия: {current or 'схема не создана'}; последняя: {head}")
            return EXIT_OK if current == head else EXIT_SCHEMA_OUTDATED
        revision = setup_database()
    except OperationalError as exc:
        print(f"ОШИБКА: PostgreSQL недоступна ({describe_connection_error(exc)})", file=sys.stderr)
        return EXIT_DATABASE_UNAVAILABLE
    except ProgrammingError as exc:
        logging.getLogger(__name__).exception("Ошибка миграции")
        print(f"ОШИБКА: миграция не применена: {exc.orig}", file=sys.stderr)
        return EXIT_MIGRATION_FAILED

    print(f"Схема БД обновлена до ревизии {revision}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
