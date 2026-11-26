"""Каталог показателей, версии наборов, нормативы, проблемы, рекомендации, мероприятия, сценарии.

Revision ID: 0006
Revises: 0005
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GROUPS = [
    ("liquidity", "Ликвидность"),
    ("stability", "Финансовая устойчивость"),
    ("profitability", "Рентабельность"),
    ("activity", "Деловая активность"),
    ("debt", "Долговая нагрузка"),
    ("cashflow", "Денежные потоки"),
    ("hr", "Кадровые показатели"),
    ("production", "Производственные показатели"),
]

# code, name, unit, group, direction
INDICATORS = [
    ("current_assets", "Оборотные активы", "RUB", "liquidity", "higher_better"),
    ("current_liabilities", "Краткосрочные обязательства", "RUB", "liquidity", "lower_better"),
    ("equity", "Собственный капитал", "RUB", "stability", "higher_better"),
    ("total_assets", "Активы", "RUB", "stability", "higher_better"),
    ("long_term_debt", "Долгосрочные обязательства", "RUB", "debt", "lower_better"),
    ("cogs", "Себестоимость", "RUB", "profitability", "lower_better"),
    ("net_profit", "Чистая прибыль", "RUB", "profitability", "higher_better"),
    ("personnel", "Численность персонала", "PCS", "hr", "neutral"),
    ("output", "Объём производства", "PCS", "production", "higher_better"),
    ("overdue_receivables", "Просроченная дебиторская задолженность", "RUB", "activity", "lower_better"),
    ("current_ratio", "Текущая ликвидность", "PCT", "liquidity", "higher_better"),
    ("quick_ratio", "Быстрая ликвидность", "PCT", "liquidity", "higher_better"),
    ("cash_ratio", "Абсолютная ликвидность", "PCT", "liquidity", "higher_better"),
    ("autonomy", "Коэффициент автономии", "PCT", "stability", "higher_better"),
    ("debt_to_equity", "Заёмный / собственный капитал", "PCT", "stability", "lower_better"),
    ("working_capital_ratio", "Обеспеченность собственными оборотными средствами", "PCT", "stability", "higher_better"),
    ("ros", "Рентабельность продаж", "PCT", "profitability", "higher_better"),
    ("roa", "Рентабельность активов", "PCT", "profitability", "higher_better"),
    ("roe", "Рентабельность собственного капитала", "PCT", "profitability", "higher_better"),
    ("receivables_turnover", "Оборачиваемость дебиторской задолженности", "PCT", "activity", "higher_better"),
    ("inventory_turnover", "Оборачиваемость запасов", "PCT", "activity", "higher_better"),
    ("asset_turnover", "Оборачиваемость активов", "PCT", "activity", "higher_better"),
    ("debt_to_capital", "Долг / капитал", "PCT", "debt", "lower_better"),
    ("debt_to_assets", "Долг / активы", "PCT", "debt", "lower_better"),
    ("cash_coverage", "Операционный поток / краткосрочные обязательства", "PCT", "cashflow", "higher_better"),
]


def upgrade() -> None:
    groups = sa.table("indicator_groups", sa.column("code"), sa.column("name"))
    op.bulk_insert(groups, [{"code": c, "name": n} for c, n in GROUPS])
    insert_indicator = sa.text(
        "INSERT INTO indicators (code, name, unit_id, group_id, impact_direction) "
        "SELECT :code, :name, u.id, g.id, :direction "
        "FROM units u, indicator_groups g WHERE u.code = :unit AND g.code = :group "
        "AND NOT EXISTS (SELECT 1 FROM indicators i WHERE i.code = :code AND i.owner_id IS NULL)"
    )
    for code, name, unit, group, direction in INDICATORS:
        op.execute(insert_indicator.bindparams(
            code=code, name=name, unit=unit, group=group, direction=direction,
        ))

    op.add_column("datasets", sa.Column("version_no", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("datasets", sa.Column("predecessor_id", sa.Integer(), nullable=True))
    op.add_column("datasets", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("datasets", sa.Column(
        "quality_status", sa.String(length=32), nullable=False, server_default="ready",
    ))
    op.drop_constraint("uq_datasets_organization_id", "datasets", type_="unique")
    op.create_unique_constraint("uq_datasets_org_name_version", "datasets", ["organization_id", "name", "version_no"])
    op.create_foreign_key(
        "fk_datasets_predecessor_id", "datasets", "datasets", ["predecessor_id"], ["id"], ondelete="SET NULL",
    )

    op.add_column("indicator_targets", sa.Column("source", sa.String(length=300), nullable=True))
    op.add_column("indicator_targets", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("indicator_targets", sa.Column("valid_from", sa.Date(), nullable=True))
    op.add_column("indicator_targets", sa.Column("valid_to", sa.Date(), nullable=True))

    op.add_column("indicator_thresholds", sa.Column("source", sa.String(length=300), nullable=True))
    op.add_column("indicator_thresholds", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("indicator_thresholds", sa.Column("methodology", sa.Text(), nullable=True))

    op.add_column("trend_results", sa.Column("abs_change", sa.Float(), nullable=True))
    op.add_column("trend_results", sa.Column("pct_change", sa.Float(), nullable=True))
    op.add_column("trend_results", sa.Column("consecutive_worsening", sa.Integer(), nullable=True))
    op.add_column("trend_results", sa.Column("label", sa.String(length=120), nullable=True))
    op.add_column("trend_results", sa.Column("significant", sa.Boolean(), nullable=True))

    op.add_column("assessments", sa.Column("history_score", sa.Numeric(5, 2), nullable=True))
    op.add_column("assessments", sa.Column("compliance_score", sa.Numeric(5, 2), nullable=True))
    op.add_column("assessments", sa.Column("completeness", sa.Numeric(6, 5), nullable=True))

    op.create_table(
        "analysis_findings",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=24), nullable=False),
        sa.Column("confidence", sa.String(length=24), nullable=False),
        sa.Column("period_label", sa.String(length=32), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("severity IN ('info', 'warning', 'high', 'critical')", name="ck_findings_severity"),
        sa.CheckConstraint(
            "confidence IN ('confirmed', 'hypothesis', 'insufficient')", name="ck_findings_confidence",
        ),
        sa.Index("ix_analysis_findings_org_run", "organization_id", "run_id"),
    )

    op.create_table(
        "analysis_alerts",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("indicator_code", sa.String(length=50), nullable=True),
        sa.Column("level", sa.String(length=24), nullable=False),
        sa.Column("rule_code", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("period_label", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("level IN ('info', 'warning', 'high', 'critical')", name="ck_alerts_level"),
        sa.Index("ix_analysis_alerts_org_run", "organization_id", "run_id"),
        sa.UniqueConstraint("run_id", "rule_code", "indicator_code", "period_label", name="uq_alerts_dedup"),
    )

    op.create_table(
        "ratio_results",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("formula", sa.Text(), nullable=False),
        sa.Column("last_value", sa.Float(), nullable=True),
        sa.Column("previous_value", sa.Float(), nullable=True),
        sa.Column("abs_change", sa.Float(), nullable=True),
        sa.Column("pct_change", sa.Float(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.UniqueConstraint("run_id", "code", name="uq_ratio_results_run_code"),
    )

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("finding_id", sa.Integer(), sa.ForeignKey("analysis_findings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("problem", sa.Text(), nullable=False),
        sa.Column("basis", sa.Text(), nullable=False),
        sa.Column("actions", sa.Text(), nullable=False),
        sa.Column("expected_result", sa.Text(), nullable=True),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="proposed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_reco_priority"),
        sa.CheckConstraint(
            "status IN ('proposed', 'accepted', 'rejected', 'converted')", name="ck_reco_status",
        ),
        sa.Index("ix_recommendations_org", "organization_id"),
    )

    op.create_table(
        "crisis_measures",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("assignee_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("run_id", sa.Integer(), sa.ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recommendation_id", sa.Integer(), sa.ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("finding_id", sa.Integer(), sa.ForeignKey("analysis_findings.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("expected_result", sa.Text(), nullable=True),
        sa.Column("success_criterion", sa.Text(), nullable=True),
        sa.Column("actual_result", sa.Text(), nullable=True),
        sa.Column("priority", sa.String(length=16), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="planned"),
        sa.Column("due_at", sa.Date(), nullable=True),
        sa.Column("indicator_codes", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("baseline_values", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_measure_priority"),
        sa.CheckConstraint(
            "status IN ('planned', 'in_progress', 'done', 'overdue', 'cancelled')",
            name="ck_measure_status",
        ),
        sa.Index("ix_crisis_measures_org", "organization_id"),
    )

    op.create_table(
        "measure_events",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("measure_id", sa.Integer(), sa.ForeignKey("crisis_measures.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Index("ix_measure_events_measure", "measure_id"),
    )

    op.create_table(
        "whatif_scenarios",
        sa.Column("id", sa.Integer(), sa.Identity(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("base_run_id", sa.Integer(), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("adjustments", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Index("ix_whatif_org", "organization_id"),
    )

    op.alter_column("audit_log", "action", existing_type=sa.String(length=50), type_=sa.String(length=80))
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
    op.create_check_constraint(
        "ck_analysis_procedures_procedure_type",
        "analysis_procedures",
        "procedure_type IN ('preprocessing', 'anomalies', 'trends', 'correlation', "
        "'clustering', 'forecasting', 'assessment', 'ratios')",
    )


ORIGINAL_INDICATOR_CODES = {
    "revenue", "sales_volume", "profit", "receivables", "payables", "inventory",
    "cash", "cf_operating", "cf_investing", "cf_financing",
}


def downgrade() -> None:
    extra_codes = [code for code, *_ in INDICATORS if code not in ORIGINAL_INDICATOR_CODES]
    for code in extra_codes:
        op.execute(sa.text("DELETE FROM indicators WHERE owner_id IS NULL AND code = :code").bindparams(code=code))
    for code, _ in GROUPS:
        op.execute(sa.text("DELETE FROM indicator_groups WHERE code = :code").bindparams(code=code))
    op.drop_column("assessments", "completeness")
    op.drop_column("assessments", "compliance_score")
    op.drop_column("assessments", "history_score")
    op.drop_column("trend_results", "significant")
    op.drop_column("trend_results", "label")
    op.drop_column("trend_results", "consecutive_worsening")
    op.drop_column("trend_results", "pct_change")
    op.drop_column("trend_results", "abs_change")
    op.drop_column("indicator_thresholds", "methodology")
    op.drop_column("indicator_thresholds", "notes")
    op.drop_column("indicator_thresholds", "source")
    op.drop_column("indicator_targets", "valid_to")
    op.drop_column("indicator_targets", "valid_from")
    op.drop_column("indicator_targets", "notes")
    op.drop_column("indicator_targets", "source")
    op.drop_table("whatif_scenarios")
    op.drop_table("measure_events")
    op.drop_table("crisis_measures")
    op.drop_table("recommendations")
    op.drop_table("ratio_results")
    op.drop_table("analysis_alerts")
    op.drop_table("analysis_findings")
    op.drop_constraint("uq_datasets_org_name_version", "datasets", type_="unique")
    op.drop_constraint("fk_datasets_predecessor_id", "datasets", type_="foreignkey")
    op.drop_column("datasets", "quality_status")
    op.drop_column("datasets", "notes")
    op.drop_column("datasets", "predecessor_id")
    op.drop_column("datasets", "version_no")
    op.create_unique_constraint("uq_datasets_organization_id", "datasets", ["organization_id", "name"])
