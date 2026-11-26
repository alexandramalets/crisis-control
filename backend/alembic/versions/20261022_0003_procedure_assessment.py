"""Добавление типа процедуры assessment.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-22 23:30:00
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CONSTRAINT = "ck_analysis_procedures_procedure_type"
TABLE = "analysis_procedures"
NEW = (
    "procedure_type IN ('preprocessing', 'anomalies', 'trends', 'correlation', "
    "'clustering', 'forecasting', 'assessment')"
)
OLD = (
    "procedure_type IN ('preprocessing', 'anomalies', 'trends', 'correlation', "
    "'clustering', 'forecasting')"
)


def _drop_procedure_type_checks() -> None:
    op.execute(
        """
        DO $$
        DECLARE rec record;
        BEGIN
          FOR rec IN
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
            WHERE nsp.nspname = current_schema()
              AND rel.relname = 'analysis_procedures'
              AND con.contype = 'c'
              AND pg_get_constraintdef(con.oid) ILIKE '%procedure_type%IN%'
          LOOP
            EXECUTE format('ALTER TABLE analysis_procedures DROP CONSTRAINT %I', rec.conname);
          END LOOP;
        END $$;
        """
    )


def upgrade() -> None:
    _drop_procedure_type_checks()
    op.create_check_constraint(CONSTRAINT, TABLE, NEW)


def downgrade() -> None:
    op.execute("DELETE FROM analysis_procedures WHERE procedure_type = 'assessment'")
    _drop_procedure_type_checks()
    op.create_check_constraint(CONSTRAINT, TABLE, OLD)
