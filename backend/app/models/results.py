"""Результаты аналитических процедур Y = {A, R, K, F, C} (ПЗ, формула 9).

Каждая процедура хранит результаты в собственных таблицах. Первичные ключи начинаются
с procedure_id, поэтому выборка результатов процедуры идёт по индексу ключа.
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, ForeignKey, ForeignKeyConstraint, Identity, Index, Integer, SmallInteger,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import AMOUNT, SCORE_100, STATISTIC, UNIT_INTERVAL, created_at_column, enum_type
from app.models.enums import PreprocessingActionType


def _procedure_fk() -> Mapped[int]:
    return mapped_column(ForeignKey("analysis_procedures.id", ondelete="CASCADE"), primary_key=True)


def _indicator_fk(primary_key: bool = True) -> Mapped[int]:
    return mapped_column(ForeignKey("indicators.id", ondelete="RESTRICT"), primary_key=primary_key)


def _period_fk(primary_key: bool = True) -> Mapped[int]:
    return mapped_column(ForeignKey("periods.id", ondelete="RESTRICT"), primary_key=primary_key)


class PreprocessingAction(Base):
    """Действие предобработки. Исходное значение не дублируется — оно в indicator_values."""

    __tablename__ = "preprocessing_actions"
    __table_args__ = (
        CheckConstraint(
            "(action = 'imputed' AND period_id IS NOT NULL AND new_value IS NOT NULL)"
            " OR (action = 'excluded' AND new_value IS NULL)",
            name="action_consistency",
        ),
        UniqueConstraint("procedure_id", "indicator_id", "period_id", postgresql_nulls_not_distinct=True),
        Index("ix_preprocessing_actions_indicator_id", "indicator_id"),
        Index("ix_preprocessing_actions_period_id", "period_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Identity(), primary_key=True)
    procedure_id: Mapped[int] = mapped_column(ForeignKey("analysis_procedures.id", ondelete="CASCADE"))
    indicator_id: Mapped[int] = mapped_column(ForeignKey("indicators.id", ondelete="RESTRICT"))
    # NULL — показатель исключён из анализа целиком
    period_id: Mapped[int | None] = mapped_column(ForeignKey("periods.id", ondelete="RESTRICT"))
    action: Mapped[PreprocessingActionType] = mapped_column(enum_type(PreprocessingActionType, "action"))
    new_value: Mapped[Decimal | None] = mapped_column(AMOUNT)


class AnomalyBaseline(Base):
    """Характерный уровень показателя и границы нормы, рассчитанные методом (формула 3)."""

    __tablename__ = "anomaly_baselines"
    __table_args__ = (
        CheckConstraint("lower_bound <= center AND center <= upper_bound", name="bounds_around_center"),
        Index("ix_anomaly_baselines_indicator_id", "indicator_id"),
    )

    procedure_id: Mapped[int] = _procedure_fk()
    indicator_id: Mapped[int] = _indicator_fk()
    center: Mapped[Decimal] = mapped_column(AMOUNT)
    lower_bound: Mapped[Decimal] = mapped_column(AMOUNT)
    upper_bound: Mapped[Decimal] = mapped_column(AMOUNT)


class AnomalyResult(Base):
    """Обнаруженная аномалия A_ij. Знак score задаёт направление отклонения."""

    __tablename__ = "anomaly_results"
    __table_args__ = (
        ForeignKeyConstraint(
            ["procedure_id", "indicator_id"],
            ["anomaly_baselines.procedure_id", "anomaly_baselines.indicator_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("score <> 0", name="score_non_zero"),
        Index("ix_anomaly_results_period_id", "period_id"),
    )

    procedure_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_id: Mapped[int] = _period_fk()
    score: Mapped[float] = mapped_column(STATISTIC)


class TrendResult(Base):
    """Тенденция показателя во времени (ПЗ 1.2, задача 2)."""

    __tablename__ = "trend_results"
    __table_args__ = (
        CheckConstraint("p_value IS NULL OR (p_value >= 0 AND p_value <= 1)", name="p_value_range"),
        CheckConstraint("kendall_tau IS NULL OR (kendall_tau >= -1 AND kendall_tau <= 1)", name="tau_range"),
        Index("ix_trend_results_indicator_id", "indicator_id"),
    )

    procedure_id: Mapped[int] = _procedure_fk()
    indicator_id: Mapped[int] = _indicator_fk()
    slope: Mapped[float] = mapped_column(STATISTIC)
    intercept: Mapped[float] = mapped_column(STATISTIC)
    kendall_tau: Mapped[float | None] = mapped_column(STATISTIC)
    p_value: Mapped[float | None] = mapped_column(STATISTIC)
    abs_change: Mapped[float | None] = mapped_column(STATISTIC)
    pct_change: Mapped[float | None] = mapped_column(STATISTIC)
    consecutive_worsening: Mapped[int | None] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(String(120))
    significant: Mapped[bool | None] = mapped_column(Boolean)


class CorrelationResult(Base):
    """Элемент верхнего треугольника корреляционной матрицы R (формула 4)."""

    __tablename__ = "correlation_results"
    __table_args__ = (
        CheckConstraint("indicator_a_id < indicator_b_id", name="ordered_pair"),
        CheckConstraint("coefficient IS NULL OR (coefficient >= -1 AND coefficient <= 1)",
                        name="coefficient_range"),
        CheckConstraint("p_value IS NULL OR (p_value >= 0 AND p_value <= 1)", name="p_value_range"),
        CheckConstraint("n_observations >= 0", name="n_observations_non_negative"),
        Index("ix_correlation_results_indicator_a_id", "indicator_a_id"),
        Index("ix_correlation_results_indicator_b_id", "indicator_b_id"),
    )

    procedure_id: Mapped[int] = _procedure_fk()
    indicator_a_id: Mapped[int] = _indicator_fk()
    indicator_b_id: Mapped[int] = _indicator_fk()
    # NULL — коэффициент не определён (например, постоянный ряд)
    coefficient: Mapped[float | None] = mapped_column(STATISTIC)
    p_value: Mapped[float | None] = mapped_column(STATISTIC)
    n_observations: Mapped[int] = mapped_column(Integer)


class Cluster(Base):
    """Кластер состояний (формула 5). label назначает сервер по центрам кластера."""

    __tablename__ = "clusters"
    __table_args__ = (
        CheckConstraint("cluster_number >= 0", name="cluster_number_non_negative"),
    )

    procedure_id: Mapped[int] = _procedure_fk()
    cluster_number: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    label: Mapped[str | None] = mapped_column(String(100))


class ClusterCentroid(Base):
    """Координата центра кластера μ_k по показателю, в единицах показателя."""

    __tablename__ = "cluster_centroids"
    __table_args__ = (
        ForeignKeyConstraint(
            ["procedure_id", "cluster_number"],
            ["clusters.procedure_id", "clusters.cluster_number"],
            ondelete="CASCADE",
        ),
        Index("ix_cluster_centroids_indicator_id", "indicator_id"),
    )

    procedure_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_number: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    indicator_id: Mapped[int] = _indicator_fk()
    value: Mapped[Decimal] = mapped_column(AMOUNT)


class ClusterMember(Base):
    """Принадлежность периода кластеру. PK (procedure_id, period_id): один период — один кластер."""

    __tablename__ = "cluster_members"
    __table_args__ = (
        ForeignKeyConstraint(
            ["procedure_id", "cluster_number"],
            ["clusters.procedure_id", "clusters.cluster_number"],
            ondelete="CASCADE",
        ),
        Index("ix_cluster_members_cluster", "procedure_id", "cluster_number"),
        Index("ix_cluster_members_period_id", "period_id"),
    )

    procedure_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_id: Mapped[int] = _period_fk()
    cluster_number: Mapped[int] = mapped_column(SmallInteger)
    # Координаты проекции на две главные компоненты — для диаграммы рассеяния
    pc1: Mapped[float | None] = mapped_column(STATISTIC)
    pc2: Mapped[float | None] = mapped_column(STATISTIC)


class ProcedureMetric(Base):
    """Метрика качества процедуры в целом (силуэт, инерция и т. п.)."""

    __tablename__ = "procedure_metrics"
    __table_args__ = (
        CheckConstraint("metric_code ~ '^[a-z][a-z0-9_]{0,49}$'", name="metric_code_format"),
    )

    procedure_id: Mapped[int] = _procedure_fk()
    metric_code: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[float] = mapped_column(STATISTIC)


class ForecastSeries(Base):
    """Прогнозная модель, выбранная для показателя, и её ошибки на отложенной выборке."""

    __tablename__ = "forecast_series"
    __table_args__ = (
        CheckConstraint("mae IS NULL OR mae >= 0", name="mae_non_negative"),
        CheckConstraint("rmse IS NULL OR rmse >= 0", name="rmse_non_negative"),
        CheckConstraint("mape IS NULL OR mape >= 0", name="mape_non_negative"),
        Index("ix_forecast_series_indicator_id", "indicator_id"),
    )

    procedure_id: Mapped[int] = _procedure_fk()
    indicator_id: Mapped[int] = _indicator_fk()
    model_name: Mapped[str] = mapped_column(String(50))
    mae: Mapped[float | None] = mapped_column(STATISTIC)
    rmse: Mapped[float | None] = mapped_column(STATISTIC)
    mape: Mapped[float | None] = mapped_column(STATISTIC)


class ForecastPoint(Base):
    """Прогнозное значение показателя на будущий период, в единицах показателя."""

    __tablename__ = "forecast_points"
    __table_args__ = (
        ForeignKeyConstraint(
            ["procedure_id", "indicator_id"],
            ["forecast_series.procedure_id", "forecast_series.indicator_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("lower_bound IS NULL OR lower_bound <= value", name="lower_not_above_value"),
        CheckConstraint("upper_bound IS NULL OR upper_bound >= value", name="upper_not_below_value"),
        Index("ix_forecast_points_period_id", "period_id"),
    )

    procedure_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    indicator_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    period_id: Mapped[int] = _period_fk()
    value: Mapped[Decimal] = mapped_column(AMOUNT)
    lower_bound: Mapped[Decimal | None] = mapped_column(AMOUNT)
    upper_bound: Mapped[Decimal | None] = mapped_column(AMOUNT)


class Assessment(Base):
    """Сводная оценка состояния C (формула 7), шкала 0–100. Уровень риска вычисляется."""

    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="score_range"),
    )

    run_id: Mapped[int] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), primary_key=True)
    score: Mapped[Decimal] = mapped_column(SCORE_100)
    history_score: Mapped[Decimal | None] = mapped_column(SCORE_100)
    compliance_score: Mapped[Decimal | None] = mapped_column(SCORE_100)
    completeness: Mapped[Decimal | None] = mapped_column(UNIT_INTERVAL)
    created_at: Mapped[datetime] = created_at_column()


class AssessmentComponent(Base):
    """Нормализованная оценка q_j по показателю исследования."""

    __tablename__ = "assessment_components"
    __table_args__ = (
        ForeignKeyConstraint(
            ["run_id", "indicator_id"],
            ["analysis_run_indicators.run_id", "analysis_run_indicators.indicator_id"],
            ondelete="CASCADE",
        ),
        CheckConstraint("normalized_score >= 0 AND normalized_score <= 1", name="score_range"),
        Index("ix_assessment_components_indicator_id", "indicator_id"),
    )

    run_id: Mapped[int] = mapped_column(ForeignKey("assessments.run_id", ondelete="CASCADE"), primary_key=True)
    indicator_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    normalized_score: Mapped[Decimal] = mapped_column(UNIT_INTERVAL)
    explanation: Mapped[str | None] = mapped_column(Text)


__all__ = [
    "PreprocessingAction", "AnomalyBaseline", "AnomalyResult", "TrendResult", "CorrelationResult",
    "Cluster", "ClusterCentroid", "ClusterMember", "ProcedureMetric", "ForecastSeries",
    "ForecastPoint", "Assessment", "AssessmentComponent",
]
