"""Уровень доступа к организации: просмотр или редактирование.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-23 16:30:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, Sequence[str], None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "organization_access",
        sa.Column("access_level", sa.String(length=16), nullable=False, server_default="view"),
    )
    op.create_check_constraint(
        "ck_organization_access_level",
        "organization_access",
        "access_level IN ('view', 'edit')",
    )
    op.execute(
        """
        UPDATE organization_access AS access
        SET access_level = 'edit'
        FROM organizations AS org
        WHERE access.organization_id = org.id AND access.user_id = org.owner_id
        """
    )


def downgrade() -> None:
    op.drop_constraint("ck_organization_access_level", "organization_access", type_="check")
    op.drop_column("organization_access", "access_level")
