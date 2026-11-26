"""Цепочка миграций без подключения к PostgreSQL.

Сравнение схемы с моделями выполняется в integration/test_migrations.py и требует тестовую БД.
"""

from alembic.script import ScriptDirectory

from app.db.migrations import alembic_config, head_revision


def test_migrations_have_single_head():
    script = ScriptDirectory.from_config(alembic_config())
    assert script.get_heads() == [head_revision()]
    assert head_revision() == "0007"


def test_migration_chain_is_linear():
    script = ScriptDirectory.from_config(alembic_config())
    revisions = list(script.walk_revisions())
    assert [revision.revision for revision in reversed(revisions)] == [
        "0001", "0002", "0003", "0004", "0005", "0006", "0007",
    ]
    assert revisions[-1].down_revision is None
