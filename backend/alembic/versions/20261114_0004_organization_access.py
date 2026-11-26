"""Назначение доступа сотрудников к организациям.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-14 12:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004"
down_revision: Union[str, Sequence[str], None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "organization_access",
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("granted_by", sa.Integer(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], name=op.f("fk_organization_access_granted_by_users"),
                                ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"],
                                name=op.f("fk_organization_access_organization_id_organizations"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_organization_access_user_id_users"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("organization_id", "user_id", name=op.f("pk_organization_access")),
    )
    op.create_index("ix_organization_access_user_id", "organization_access", ["user_id"], unique=False)
    op.execute(
        """
        INSERT INTO organization_access (organization_id, user_id, granted_by, granted_at)
        SELECT id, owner_id, owner_id, created_at FROM organizations
        """
    )


def downgrade() -> None:
    op.drop_index("ix_organization_access_user_id", table_name="organization_access")
    op.drop_table("organization_access")
