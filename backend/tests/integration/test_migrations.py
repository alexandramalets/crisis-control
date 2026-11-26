from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import text

import app.models  # noqa: F401
from app.db.base import Base
from app.db.migrations import current_revision, head_revision


def test_schema_is_at_head(engine):
    with engine.connect() as connection:
        assert current_revision(connection) == head_revision()


def test_migrations_match_models(engine):
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


def test_reference_data_seeded(engine):
    with engine.connect() as connection:
        roles = connection.scalars(text("SELECT code FROM roles ORDER BY code")).all()
        indicators = connection.scalar(text("SELECT count(*) FROM indicators WHERE owner_id IS NULL"))
        users = connection.scalar(text("SELECT count(*) FROM users"))
    assert roles == ["admin", "analyst"]
    assert indicators == 35
    assert users == 0, "миграции не создают учётных записей"
