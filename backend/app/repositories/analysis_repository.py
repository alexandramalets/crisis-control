from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased, selectinload

from app.models import (
    AnalysisProcedure, AnalysisRun, AnalysisRunIndicator, AnomalyBaseline, AnomalyResult, Assessment,
    AssessmentComponent, Cluster, ClusterCentroid, ClusterMember, CorrelationResult, Dataset, ForecastPoint,
    ForecastSeries, Indicator, IndicatorThreshold, IndicatorValue, Organization, Period, ProcedureMetric,
    RatioResult, TrendResult,
)
from app.models.enums import AnalysisStatus, ProcedureType
from app.repositories.visibility import visible_organization_clause

PeriodFrom = aliased(Period)
PeriodTo = aliased(Period)


class AnalysisRepository:
    def __init__(self, session: Session):
        self.session = session

    def _summary_query(self, owner_id: int | None):
        query = (
            select(
                AnalysisRun.id, AnalysisRun.dataset_id, Dataset.name.label("dataset_name"),
                Dataset.organization_id, Organization.name.label("organization_name"),
                AnalysisRun.created_by, AnalysisRun.parent_run_id,
                AnalysisRun.status, PeriodFrom.start_date.label("period_from"),
                PeriodTo.end_date.label("period_to"), AnalysisRun.created_at, AnalysisRun.finished_at,
            )
            .join(Dataset, Dataset.id == AnalysisRun.dataset_id)
            .join(Organization, Organization.id == Dataset.organization_id)
            .join(PeriodFrom, PeriodFrom.id == AnalysisRun.period_from_id)
            .join(PeriodTo, PeriodTo.id == AnalysisRun.period_to_id)
        )
        clause = visible_organization_clause(owner_id)
        if clause is not None:
            query = query.where(clause)
        return query

    def find(self, owner_id: int | None, dataset_id: int | None, organization_id: int | None,
             status: AnalysisStatus | None, limit: int, offset: int) -> tuple[list[dict], int]:
        query = self._summary_query(owner_id)
        if dataset_id is not None:
            query = query.where(AnalysisRun.dataset_id == dataset_id)
        if organization_id is not None:
            query = query.where(Dataset.organization_id == organization_id)
        if status is not None:
            query = query.where(AnalysisRun.status == status)
        total = self.session.scalar(select(func.count()).select_from(query.subquery()))
        query = query.order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc()).limit(limit).offset(offset)
        return [dict(row) for row in self.session.execute(query).mappings()], total or 0

    def get_summary(self, run_id: int, owner_id: int | None) -> dict | None:
        row = self.session.execute(self._summary_query(owner_id).where(AnalysisRun.id == run_id)).mappings().first()
        return dict(row) if row else None

    def get_run(self, run_id: int) -> AnalysisRun | None:
        query = (
            select(AnalysisRun).where(AnalysisRun.id == run_id)
            .options(selectinload(AnalysisRun.procedures).selectinload(AnalysisProcedure.parameters))
        )
        return self.session.scalar(query)

    def run_indicators(self, run_id: int) -> list[dict]:
        query = (
            select(AnalysisRunIndicator.indicator_id, Indicator.code, Indicator.name, AnalysisRunIndicator.weight)
            .join(Indicator, Indicator.id == AnalysisRunIndicator.indicator_id)
            .where(AnalysisRunIndicator.run_id == run_id)
            .order_by(Indicator.code)
        )
        return [dict(row) for row in self.session.execute(query).mappings()]

    def add_run(self, run: AnalysisRun) -> AnalysisRun:
        self.session.add(run)
        self.session.flush()
        return run

    def delete_run(self, run: AnalysisRun) -> None:
        self.session.delete(run)
        self.session.flush()

    def procedure(self, run_id: int, procedure_type: ProcedureType) -> AnalysisProcedure | None:
        query = select(AnalysisProcedure).where(
            AnalysisProcedure.run_id == run_id, AnalysisProcedure.procedure_type == procedure_type,
        )
        return self.session.scalar(query)

    def matrix_rows(self, dataset_id: int, indicator_ids: list[int],
                    period_from: date, period_to: date) -> list[dict]:
        query = (
            select(
                IndicatorValue.indicator_id, IndicatorValue.period_id,
                Period.start_date, func.sum(IndicatorValue.value).label("value"),
            )
            .join(Period, Period.id == IndicatorValue.period_id)
            .where(
                IndicatorValue.dataset_id == dataset_id,
                IndicatorValue.indicator_id.in_(indicator_ids),
                Period.start_date >= period_from,
                Period.start_date <= period_to,
            )
            .group_by(IndicatorValue.indicator_id, IndicatorValue.period_id, Period.start_date)
            .order_by(Period.start_date, IndicatorValue.indicator_id)
        )
        return [dict(row) for row in self.session.execute(query).mappings()]

    def thresholds(self, organization_id: int, indicator_ids: list[int]) -> dict[int, tuple]:
        query = select(IndicatorThreshold).where(
            IndicatorThreshold.organization_id == organization_id,
            IndicatorThreshold.indicator_id.in_(indicator_ids),
        )
        return {
            row.indicator_id: (row.lower_bound, row.upper_bound)
            for row in self.session.scalars(query)
        }

    def dataset_indicators(self, dataset_id: int) -> list[Indicator]:
        query = (
            select(Indicator).join(IndicatorValue, IndicatorValue.indicator_id == Indicator.id)
            .where(IndicatorValue.dataset_id == dataset_id)
            .distinct().order_by(Indicator.code)
        )
        return list(self.session.scalars(query))

    def anomaly_rows(self, procedure_id: int) -> list[dict]:
        query = (
            select(
                Indicator.code.label("indicator"), Indicator.name.label("indicator_name"),
                Period.start_date.label("period_start"), AnomalyResult.score,
                AnomalyBaseline.center, AnomalyBaseline.lower_bound, AnomalyBaseline.upper_bound,
                AnomalyResult.indicator_id, AnomalyResult.period_id, AnomalyResult.procedure_id,
            )
            .join(Indicator, Indicator.id == AnomalyResult.indicator_id)
            .join(Period, Period.id == AnomalyResult.period_id)
            .join(
                AnomalyBaseline,
                (AnomalyBaseline.procedure_id == AnomalyResult.procedure_id)
                & (AnomalyBaseline.indicator_id == AnomalyResult.indicator_id),
            )
            .where(AnomalyResult.procedure_id == procedure_id)
            .order_by(Period.start_date, Indicator.code)
        )
        return [dict(row) for row in self.session.execute(query).mappings()]

    def anomaly_baselines(self, procedure_id: int) -> list[dict]:
        query = (
            select(
                Indicator.code.label("indicator"), AnomalyBaseline.center,
                AnomalyBaseline.lower_bound, AnomalyBaseline.upper_bound,
            )
            .join(Indicator, Indicator.id == AnomalyBaseline.indicator_id)
            .where(AnomalyBaseline.procedure_id == procedure_id)
            .order_by(Indicator.code)
        )
        return [dict(row) for row in self.session.execute(query).mappings()]

    def correlation_rows(self, procedure_id: int) -> list[dict]:
        indicator_a = aliased(Indicator)
        indicator_b = aliased(Indicator)
        query = (
            select(
                indicator_a.code.label("indicator_a"), indicator_b.code.label("indicator_b"),
                CorrelationResult.coefficient, CorrelationResult.p_value, CorrelationResult.n_observations,
            )
            .join(indicator_a, indicator_a.id == CorrelationResult.indicator_a_id)
            .join(indicator_b, indicator_b.id == CorrelationResult.indicator_b_id)
            .where(CorrelationResult.procedure_id == procedure_id)
            .order_by(indicator_a.code, indicator_b.code)
        )
        return [dict(row) for row in self.session.execute(query).mappings()]

    def clusters(self, procedure_id: int) -> list[Cluster]:
        query = select(Cluster).where(Cluster.procedure_id == procedure_id).order_by(Cluster.cluster_number)
        return list(self.session.scalars(query))

    def cluster_centroids(self, procedure_id: int) -> list[dict]:
        query = (
            select(ClusterCentroid.cluster_number, Indicator.code.label("indicator"), ClusterCentroid.value)
            .join(Indicator, Indicator.id == ClusterCentroid.indicator_id)
            .where(ClusterCentroid.procedure_id == procedure_id)
            .order_by(ClusterCentroid.cluster_number, Indicator.code)
        )
        return [dict(row) for row in self.session.execute(query).mappings()]

    def cluster_members(self, procedure_id: int) -> list[dict]:
        query = (
            select(
                Period.start_date.label("period_start"), ClusterMember.cluster_number,
                ClusterMember.pc1, ClusterMember.pc2,
            )
            .join(Period, Period.id == ClusterMember.period_id)
            .where(ClusterMember.procedure_id == procedure_id)
            .order_by(Period.start_date)
        )
        return [dict(row) for row in self.session.execute(query).mappings()]

    def metrics(self, procedure_id: int) -> dict[str, float]:
        query = select(ProcedureMetric).where(ProcedureMetric.procedure_id == procedure_id)
        return {row.metric_code: row.value for row in self.session.scalars(query)}

    def forecast_series(self, procedure_id: int) -> list[dict]:
        query = (
            select(
                Indicator.code.label("indicator"), ForecastSeries.model_name,
                ForecastSeries.mae, ForecastSeries.rmse, ForecastSeries.mape,
            )
            .join(Indicator, Indicator.id == ForecastSeries.indicator_id)
            .where(ForecastSeries.procedure_id == procedure_id)
            .order_by(Indicator.code)
        )
        return [dict(row) for row in self.session.execute(query).mappings()]

    def forecast_points(self, procedure_id: int) -> list[dict]:
        query = (
            select(
                Indicator.code.label("indicator"), Period.start_date.label("period_start"),
                ForecastPoint.value, ForecastPoint.lower_bound, ForecastPoint.upper_bound,
            )
            .join(Indicator, Indicator.id == ForecastPoint.indicator_id)
            .join(Period, Period.id == ForecastPoint.period_id)
            .where(ForecastPoint.procedure_id == procedure_id)
            .order_by(Indicator.code, Period.start_date)
        )
        return [dict(row) for row in self.session.execute(query).mappings()]

    def assessment(self, run_id: int) -> Assessment | None:
        return self.session.get(Assessment, run_id)

    def assessment_components(self, run_id: int) -> list[dict]:
        query = (
            select(
                Indicator.code.label("indicator"), Indicator.name.label("indicator_name"),
                AssessmentComponent.normalized_score, AssessmentComponent.explanation,
                AnalysisRunIndicator.weight,
            )
            .join(Indicator, Indicator.id == AssessmentComponent.indicator_id)
            .join(
                AnalysisRunIndicator,
                (AnalysisRunIndicator.run_id == AssessmentComponent.run_id)
                & (AnalysisRunIndicator.indicator_id == AssessmentComponent.indicator_id),
            )
            .where(AssessmentComponent.run_id == run_id)
            .order_by(Indicator.code)
        )
        return [dict(row) for row in self.session.execute(query).mappings()]

    def trend_rows(self, procedure_id: int) -> list[dict]:
        query = (
            select(
                Indicator.code.label("indicator"), TrendResult.slope, TrendResult.intercept,
                TrendResult.kendall_tau, TrendResult.p_value, TrendResult.abs_change,
                TrendResult.pct_change, TrendResult.consecutive_worsening, TrendResult.label,
                TrendResult.significant,
            )
            .join(Indicator, Indicator.id == TrendResult.indicator_id)
            .where(TrendResult.procedure_id == procedure_id)
            .order_by(Indicator.code)
        )
        return [dict(row) for row in self.session.execute(query).mappings()]

    def ratio_rows(self, run_id: int) -> list[dict]:
        query = (
            select(
                RatioResult.code, RatioResult.name, RatioResult.category, RatioResult.formula,
                RatioResult.last_value, RatioResult.previous_value, RatioResult.abs_change,
                RatioResult.pct_change, RatioResult.payload,
            )
            .where(RatioResult.run_id == run_id)
            .order_by(RatioResult.code)
        )
        return [dict(row) for row in self.session.execute(query).mappings()]

