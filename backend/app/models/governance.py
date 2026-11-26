from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Identity, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import created_at_column


class AnalysisFinding(Base):
    __tablename__ = "analysis_findings"
    __table_args__ = (
        Index("ix_analysis_findings_org_run", "organization_id", "run_id"),
        CheckConstraint("severity IN ('info', 'warning', 'high', 'critical')", name="ck_findings_severity"),
        CheckConstraint(
            "confidence IN ('confirmed', 'hypothesis', 'insufficient')", name="ck_findings_confidence",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(24))
    confidence: Mapped[str] = mapped_column(String(24))
    period_label: Mapped[str | None] = mapped_column(String(32))
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = created_at_column()


class AnalysisAlert(Base):
    __tablename__ = "analysis_alerts"
    __table_args__ = (
        Index("ix_analysis_alerts_org_run", "organization_id", "run_id"),
        UniqueConstraint("run_id", "rule_code", "indicator_code", "period_label", name="uq_alerts_dedup"),
        CheckConstraint("level IN ('info', 'warning', 'high', 'critical')", name="ck_alerts_level"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    indicator_code: Mapped[str | None] = mapped_column(String(50))
    level: Mapped[str] = mapped_column(String(24))
    rule_code: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    basis: Mapped[str] = mapped_column(Text)
    action: Mapped[str | None] = mapped_column(Text)
    period_label: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = created_at_column()


class RatioResult(Base):
    __tablename__ = "ratio_results"
    __table_args__ = (
        UniqueConstraint("run_id", "code", name="uq_ratio_results_run_code"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(32))
    formula: Mapped[str] = mapped_column(Text)
    last_value: Mapped[float | None] = mapped_column(Float)
    previous_value: Mapped[float | None] = mapped_column(Float)
    abs_change: Mapped[float | None] = mapped_column(Float)
    pct_change: Mapped[float | None] = mapped_column(Float)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Recommendation(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        Index("ix_recommendations_org", "organization_id"),
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_reco_priority"),
        CheckConstraint(
            "status IN ('proposed', 'accepted', 'rejected', 'converted')", name="ck_reco_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    finding_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_findings.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    problem: Mapped[str] = mapped_column(Text)
    basis: Mapped[str] = mapped_column(Text)
    actions: Mapped[str] = mapped_column(Text)
    expected_result: Mapped[str | None] = mapped_column(Text)
    limitations: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(24), default="proposed")
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CrisisMeasure(Base):
    __tablename__ = "crisis_measures"
    __table_args__ = (
        Index("ix_crisis_measures_org", "organization_id"),
        CheckConstraint("priority IN ('low', 'medium', 'high')", name="ck_measure_priority"),
        CheckConstraint(
            "status IN ('planned', 'in_progress', 'done', 'overdue', 'cancelled')",
            name="ck_measure_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    assignee_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_runs.id", ondelete="SET NULL"))
    recommendation_id: Mapped[int | None] = mapped_column(ForeignKey("recommendations.id", ondelete="SET NULL"))
    finding_id: Mapped[int | None] = mapped_column(ForeignKey("analysis_findings.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    expected_result: Mapped[str | None] = mapped_column(Text)
    success_criterion: Mapped[str | None] = mapped_column(Text)
    actual_result: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(16), default="medium")
    status: Mapped[str] = mapped_column(String(24), default="planned")
    due_at: Mapped[date | None] = mapped_column(Date)
    indicator_codes: Mapped[list] = mapped_column(JSON, default=list)
    baseline_values: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = created_at_column()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class MeasureEvent(Base):
    __tablename__ = "measure_events"
    __table_args__ = (
        Index("ix_measure_events_measure", "measure_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    measure_id: Mapped[int] = mapped_column(ForeignKey("crisis_measures.id", ondelete="CASCADE"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(40))
    comment: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = created_at_column()


class WhatIfScenario(Base):
    __tablename__ = "whatif_scenarios"
    __table_args__ = (
        Index("ix_whatif_org", "organization_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    base_run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    adjustments: Mapped[list] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = created_at_column()
