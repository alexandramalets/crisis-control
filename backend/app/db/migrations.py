"""Программное управление схемой БД через Alembic."""

import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

logging.getLogger("alembic.runtime.plugins").setLevel(logging.WARNING)


def alembic_config(connection: Connection | None = None) -> Config:
    config = Config(str(ALEMBIC_INI))
    # Логирование уже настроено приложением — не переопределять его из alembic.ini
    config.attributes["configure_logger"] = False
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def head_revision() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def current_revision(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


def upgrade_to_head(connection: Connection | None = None) -> None:
    command.upgrade(alembic_config(connection), "head")


def downgrade_to_base(connection: Connection | None = None) -> None:
    command.downgrade(alembic_config(connection), "base")
