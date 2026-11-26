"""Связь журнала действий с организацией.

Revision ID: 0007
Revises: 0006
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, Sequence[str], None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audit_log", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_audit_log_organization_id",
        "audit_log",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_audit_log_organization_id_created_at",
        "audit_log",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_log_organization_id_created_at", table_name="audit_log")
    op.drop_constraint("fk_audit_log_organization_id", "audit_log", type_="foreignkey")
    op.drop_column("audit_log", "organization_id")
