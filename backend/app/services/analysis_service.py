"""Запуск исследований: доступ, параметры, вызов ML-адаптера, сохранение статуса и результатов."""

import logging
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.integrations.analytics_client import AnalyticsClient, AnalyticsServiceError, get_analytics_client
from app.integrations.analytics_contracts import AnalyzeResponse, ProcedureEnvelope
from app.models import (
    AnalysisParameter, AnalysisProcedure, AnalysisRun, AnalysisRunIndicator, Dataset, Indicator, IndicatorValue,
    Organization,
)
from app.models.enums import AnalysisStatus, PeriodGranularity, ProcedureStatus, ProcedureType
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.audit_repository import AuditRepository
from app.schemas.analysis import (
    AnalysisConclusion, AnalysisCreate, AnalysisDetail, AnalysisIndicatorIn, AnalysisIndicatorRead,
    AnalysisProcedureRead, AnalysisResults, AnalysisSummary, AnomalyItem, AnomalyParams, AnomalyResults,
    AssessmentComponentRead, AssessmentResults, ClusteringParams, ClusterMemberRead, ClusterProfile, ClusterResults,
    CorrelationItem, CorrelationParams, CorrelationResults, ForecastParams, ForecastPointRead, ForecastResults,
    ForecastSeriesRead, RatioItemRead, RatioResults, TrendItemRead, TrendResults,
)
from app.services.assessment_labels import ASSESSMENT_DISCLAIMER, ASSESSMENT_METHOD, interpret_score
from app.services.narratives import (
    anomalies_narrative, assessment_narrative, clustering_narrative, correlation_narrative, forecast_narrative,
)
from app.schemas.common import Page
from app.services.access import AccessContext
from app.services.analysis_persist import ML_TO_DB, add_parameter, persist_procedures
from app.services.dataset_service import DatasetService
from app.services.errors import (
    AnalyticsContractError, AnalyticsUnavailableError, NotFoundError, ValidationFailedError,
)
from app.services.organization_service import OrganizationService

logger = logging.getLogger(__name__)

NOT_FOUND = "Исследование не найдено"
DEFAULT_PROCEDURES = (
    "validate", "ratios", "anomalies", "trends", "correlation", "clustering", "forecast", "assessment",
)
MIN_PERIODS = 3


def format_period(start: date, granularity: PeriodGranularity) -> str:
    if granularity == PeriodGranularity.MONTH:
        return start.strftime("%Y-%m")
    if granularity == PeriodGranularity.QUARTER:
        return f"{start.year}-Q{(start.month - 1) // 3 + 1}"
    return str(start.year)


def _weight(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)


class AnalysisService:
    def __init__(self, session: Session, settings: Settings | None = None, client: AnalyticsClient | None = None):
        self.session = session
        self.settings = settings or get_settings()
        self.client = client or get_analytics_client(self.settings)
        self.analyses = AnalysisRepository(session)
        self.audit = AuditRepository(session)

    def search(self, ctx: AccessContext, dataset_id: int | None, organization_id: int | None,
             status: AnalysisStatus | None, limit: int, offset: int) -> Page[AnalysisSummary]:
        ctx.ensure_analyst()
        if dataset_id is not None:
            DatasetService(self.session).get_visible(ctx, dataset_id)
        if organization_id is not None:
            OrganizationService(self.session).get_visible(ctx, organization_id)
        rows, total = self.analyses.find(ctx.read_scope, dataset_id, organization_id, status, limit, offset)
        return Page(items=[AnalysisSummary(**row) for row in rows], total=total, limit=limit, offset=offset)

    def ensure_visible(self, ctx: AccessContext, run_id: int) -> dict:
        ctx.ensure_analyst()
        summary = self.analyses.get_summary(run_id, ctx.read_scope)
        if summary is None:
            raise NotFoundError(NOT_FOUND)
        return summary

    def detail(self, ctx: AccessContext, run_id: int) -> AnalysisDetail:
        summary = self.ensure_visible(ctx, run_id)
        run = self.analyses.get_run(run_id)
        return AnalysisDetail(
            **summary,
            random_state=run.random_state,
            analytics_service_version=run.analytics_service_version,
            error_message=run.error_message,
            started_at=run.started_at,
            indicators=[AnalysisIndicatorRead(**row) for row in self.analyses.run_indicators(run_id)],
            procedures=[AnalysisProcedureRead.model_validate(p) for p in run.procedures],
        )

    def methods(self, ctx: AccessContext) -> dict:
        ctx.ensure_analyst()
        try:
            return self.client.get_capabilities()
        except AnalyticsServiceError as exc:
            logger.warning("Не удалось получить capabilities: %s", exc.message)
            raise AnalyticsUnavailableError(exc.message) from exc

    def start(self, ctx: AccessContext, data: AnalysisCreate) -> AnalysisDetail:
        dataset, indicators, period_from, period_to, selected = self._prepare(ctx, data)
        run = self._create_run(ctx, dataset, data, indicators, period_from, period_to, selected)
        self.audit.add(
            "analysis_started", ctx.user_id, "analysis_run", run.id,
            organization_id=dataset.organization_id,
        )
        run_id = run.id
        dataset_id = dataset.id
        self.session.commit()
        run = self.analyses.get_run(run_id)
        dataset = self.session.get(Dataset, dataset_id)
        self._execute(run, dataset, indicators, period_from, period_to, selected, data)
        self.session.commit()
        run = self.analyses.get_run(run_id)
        if run.status == AnalysisStatus.FAILED:
            message = run.error_message or "Аналитический сервис недоступен. Повторите попытку позже."
            error_cls = AnalyticsContractError if "некорректн" in message.lower() else AnalyticsUnavailableError
            raise error_cls(message, details={"run_id": run.id, "status": run.status.value})
        return self.detail(ctx, run.id)

    def rerun(self, ctx: AccessContext, run_id: int, data: AnalysisCreate | None) -> AnalysisDetail:
        original = self.detail(ctx, run_id)
        dataset = DatasetService(self.session).get_visible(ctx, original.dataset_id)
        OrganizationService(self.session).get_modifiable(ctx, dataset.organization_id)
        payload = data or AnalysisCreate(dataset_id=original.dataset_id)
        payload.dataset_id = original.dataset_id
        payload.parent_run_id = original.id
        if payload.period_from is None:
            payload.period_from = original.period_from
        if payload.period_to is None:
            payload.period_to = original.period_to
        if payload.indicators is None:
            payload.indicators = [
                AnalysisIndicatorIn(code=item.code, weight=item.weight) for item in original.indicators
            ]
        return self.start(ctx, payload)

    def delete(self, ctx: AccessContext, run_id: int) -> None:
        summary = self.ensure_visible(ctx, run_id)
        dataset = DatasetService(self.session).get_visible(ctx, summary["dataset_id"])
        OrganizationService(self.session).get_modifiable(ctx, dataset.organization_id)
        run = self.analyses.get_run(run_id)
        self.analyses.delete_run(run)
        self.audit.add(
            "analysis_deleted", ctx.user_id, "analysis_run", run_id,
            organization_id=dataset.organization_id,
        )
        self.session.commit()

    def results(self, ctx: AccessContext, run_id: int) -> AnalysisResults:
        detail = self.detail(ctx, run_id)
        anomalies = self.anomalies(ctx, run_id) if self.analyses.procedure(run_id, ProcedureType.ANOMALIES) else None
        correlation = self.correlations(ctx, run_id) if self.analyses.procedure(run_id, ProcedureType.CORRELATION) else None
        clustering = self.clusters(ctx, run_id) if self.analyses.procedure(run_id, ProcedureType.CLUSTERING) else None
        forecast = self.forecasts(ctx, run_id) if self.analyses.procedure(run_id, ProcedureType.FORECASTING) else None
        assessment = self.assessment(ctx, run_id) if self.analyses.procedure(run_id, ProcedureType.ASSESSMENT) else None
        trends = self.trends(ctx, run_id) if self.analyses.procedure(run_id, ProcedureType.TRENDS) else None
        ratios = self.ratios(ctx, run_id)
        findings, alerts = self._governance_rows(run_id)
        return AnalysisResults(
            run=detail,
            anomalies=anomalies,
            correlation=correlation,
            clustering=clustering,
            forecast=forecast,
            assessment=assessment,
            trends=trends,
            ratios=ratios,
            findings=findings,
            alerts=alerts,
            conclusion=build_conclusion(detail, assessment, anomalies, correlation, clustering, forecast),
            assessment_narrative=assessment_narrative(
                assessment, organization_name=getattr(detail, "organization_name", None),
            ),
            anomalies_narrative=anomalies_narrative(anomalies),
            correlation_narrative=correlation_narrative(correlation),
            clustering_narrative=clustering_narrative(clustering),
            forecast_narrative=forecast_narrative(forecast),
        )

    def anomalies(self, ctx: AccessContext, run_id: int) -> AnomalyResults:
        run, procedure = self._procedure(ctx, run_id, ProcedureType.ANOMALIES)
        if procedure.status != ProcedureStatus.OK:
            return AnomalyResults(status=procedure.status, message=procedure.message, method=procedure.method,
                                  items=[], baselines=[])
        items = []
        for row in self.analyses.anomaly_rows(procedure.id):
            value = self.session.scalar(
                select(func.sum(IndicatorValue.value)).where(
                    IndicatorValue.dataset_id == run.dataset_id,
                    IndicatorValue.indicator_id == row["indicator_id"],
                    IndicatorValue.period_id == row["period_id"],
                )
            )
            baseline = row["center"]
            items.append(AnomalyItem(
                indicator=row["indicator"], indicator_name=row["indicator_name"],
                period_start=row["period_start"], value=value, baseline=baseline,
                deviation=None if value is None else value - baseline,
                score=row["score"], direction="above" if row["score"] > 0 else "below",
                lower_bound=row["lower_bound"], upper_bound=row["upper_bound"],
            ))
        return AnomalyResults(
            status=procedure.status, message=procedure.message, method=procedure.method,
            items=items, baselines=self.analyses.anomaly_baselines(procedure.id),
        )

    def correlations(self, ctx: AccessContext, run_id: int) -> CorrelationResults:
        _, procedure = self._procedure(ctx, run_id, ProcedureType.CORRELATION)
        pairs = [CorrelationItem(**row) for row in self.analyses.correlation_rows(procedure.id)] if procedure.status == ProcedureStatus.OK else []
        return CorrelationResults(status=procedure.status, message=procedure.message, pairs=pairs)

    def clusters(self, ctx: AccessContext, run_id: int) -> ClusterResults:
        _, procedure = self._procedure(ctx, run_id, ProcedureType.CLUSTERING)
        if procedure.status != ProcedureStatus.OK:
            return ClusterResults(status=procedure.status, message=procedure.message, metrics={}, clusters=[], members=[])
        centroids = defaultdict(dict)
        sizes = defaultdict(int)
        for row in self.analyses.cluster_centroids(procedure.id):
            centroids[row["cluster_number"]][row["indicator"]] = row["value"]
        members = [
            ClusterMemberRead(period_start=row["period_start"], cluster=row["cluster_number"],
                              pc1=row["pc1"], pc2=row["pc2"])
            for row in self.analyses.cluster_members(procedure.id)
        ]
        for member in members:
            sizes[member.cluster] += 1
        clusters = [
            ClusterProfile(cluster=c.cluster_number, label=c.label, size=sizes[c.cluster_number],
                           centroid=centroids[c.cluster_number])
            for c in self.analyses.clusters(procedure.id)
        ]
        return ClusterResults(
            status=procedure.status, message=procedure.message,
            metrics=self.analyses.metrics(procedure.id), clusters=clusters, members=members,
        )

    def forecasts(self, ctx: AccessContext, run_id: int) -> ForecastResults:
        _, procedure = self._procedure(ctx, run_id, ProcedureType.FORECASTING)
        if procedure.status != ProcedureStatus.OK:
            return ForecastResults(status=procedure.status, message=procedure.message, series=[])
        points = defaultdict(list)
        for row in self.analyses.forecast_points(procedure.id):
            points[row["indicator"]].append(ForecastPointRead(
                period_start=row["period_start"], value=row["value"],
                lower_bound=row["lower_bound"], upper_bound=row["upper_bound"],
            ))
        series = [
            ForecastSeriesRead(indicator=row["indicator"], method=row["model_name"], points=points[row["indicator"]])
            for row in self.analyses.forecast_series(procedure.id)
        ]
        return ForecastResults(status=procedure.status, message=procedure.message, series=series)

    def assessment(self, ctx: AccessContext, run_id: int) -> AssessmentResults:
        _, procedure = self._procedure(ctx, run_id, ProcedureType.ASSESSMENT)
        stored = self.analyses.assessment(run_id)
        if procedure.status != ProcedureStatus.OK or stored is None:
            return AssessmentResults(
                status=procedure.status if procedure.status != ProcedureStatus.OK else ProcedureStatus.SKIPPED,
                message=procedure.message or "Недостаточно данных",
                status_label="Недостаточно данных", score=None, components=[],
            )
        components = []
        for row in self.analyses.assessment_components(run_id):
            weight = row["weight"]
            normalized = row["normalized_score"]
            contribution = None
            if weight is not None and normalized is not None:
                contribution = (Decimal(weight) * Decimal(normalized) * Decimal(100)).quantize(Decimal("0.01"))
            components.append(AssessmentComponentRead(
                indicator=row["indicator"], indicator_name=row["indicator_name"],
                weight=weight, normalized_score=normalized, contribution=contribution,
                explanation=row["explanation"],
            ))
        return AssessmentResults(
            status=procedure.status, message=procedure.message, status_label="Рассчитано",
            score=stored.score, history_score=stored.history_score, compliance_score=stored.compliance_score,
            completeness=stored.completeness, interpretation=interpret_score(stored.score),
            methodology=ASSESSMENT_METHOD, disclaimer=ASSESSMENT_DISCLAIMER, components=components,
        )

    def trends(self, ctx: AccessContext, run_id: int) -> TrendResults:
        _, procedure = self._procedure(ctx, run_id, ProcedureType.TRENDS)
        items = [TrendItemRead(**row) for row in self.analyses.trend_rows(procedure.id)] if procedure.status == ProcedureStatus.OK else []
        return TrendResults(status=procedure.status, message=procedure.message, items=items)

    def ratios(self, ctx: AccessContext, run_id: int) -> RatioResults:
        self.ensure_visible(ctx, run_id)
        procedure = self.analyses.procedure(run_id, ProcedureType.RATIOS)
        items = [RatioItemRead(**row) for row in self.analyses.ratio_rows(run_id)]
        return RatioResults(
            status=procedure.status if procedure else None,
            message=procedure.message if procedure else None,
            items=items,
        )

    def _governance_rows(self, run_id: int) -> tuple[list[dict], list[dict]]:
        from app.models import AnalysisAlert, AnalysisFinding
        findings = [
            {
                "id": row.id, "code": row.code, "title": row.title, "description": row.description,
                "severity": row.severity, "confidence": row.confidence, "period_label": row.period_label,
                "evidence": row.evidence or {},
            }
            for row in self.session.scalars(
                select(AnalysisFinding).where(AnalysisFinding.run_id == run_id).order_by(AnalysisFinding.id)
            )
        ]
        alerts = [
            {
                "id": row.id, "indicator_code": row.indicator_code, "level": row.level,
                "rule_code": row.rule_code, "message": row.message, "basis": row.basis,
                "action": row.action, "period_label": row.period_label,
            }
            for row in self.session.scalars(
                select(AnalysisAlert).where(AnalysisAlert.run_id == run_id).order_by(AnalysisAlert.id)
            )
        ]
        return findings, alerts

    def _procedure(self, ctx: AccessContext, run_id: int, procedure_type: ProcedureType):
        self.ensure_visible(ctx, run_id)
        run = self.analyses.get_run(run_id)
        procedure = self.analyses.procedure(run_id, procedure_type)
        if procedure is None:
            raise NotFoundError("Результаты процедуры не найдены")
        return run, procedure

    def _prepare(self, ctx: AccessContext, data: AnalysisCreate):
        dataset = DatasetService(self.session).get_visible(ctx, data.dataset_id)
        OrganizationService(self.session).get_modifiable(ctx, dataset.organization_id)
        if data.parent_run_id is not None:
            parent = self.ensure_visible(ctx, data.parent_run_id)
            if parent["dataset_id"] != dataset.id:
                raise ValidationFailedError("Повторный запуск должен относиться к тому же набору данных")
        available = {item.code: item for item in self.analyses.dataset_indicators(dataset.id)}
        if not available:
            raise ValidationFailedError("В наборе данных нет показателей")
        selected_meta = data.indicators or [
            AnalysisIndicatorIn(code=code) for code in available
        ]
        indicators: list[tuple[Indicator, Decimal]] = []
        for item in selected_meta:
            indicator = available.get(item.code) if item.code else next(
                (ind for ind in available.values() if ind.id == item.indicator_id), None,
            )
            if indicator is None:
                raise ValidationFailedError("Показатель отсутствует в наборе данных",
                                            details={"code": item.code, "indicator_id": item.indicator_id})
            indicators.append((indicator, item.weight))
        codes = [ind.code for ind, _ in indicators]
        if len(codes) != len(set(codes)):
            raise ValidationFailedError("Показатели в исследовании не должны повторяться")
        n = len(indicators)
        resolved = []
        for indicator, weight in indicators:
            resolved.append((indicator, _weight(Decimal(1) / n if weight is None else weight)))
        if all(weight == 0 for _, weight in resolved):
            raise ValidationFailedError("Сумма весов должна быть больше нуля")
        period_from, period_to, _ = DatasetService(self.session).datasets.period_range(dataset.id)
        if period_from is None:
            raise ValidationFailedError("В наборе данных нет периодов")
        start = data.period_from or period_from
        end = data.period_to or period_to
        if start < period_from or end > period_to:
            raise ValidationFailedError("Запрошенный интервал выходит за пределы набора данных")
        selected = tuple(data.procedures) if data.procedures else DEFAULT_PROCEDURES
        if "validate" not in selected:
            selected = ("validate",) + selected
        rows = self.analyses.matrix_rows(dataset.id, [indicator.id for indicator, _ in resolved], start, end)
        n_periods = len({row["start_date"] for row in rows})
        if n_periods < MIN_PERIODS:
            raise ValidationFailedError(f"Недостаточно периодов для анализа (нужно не менее {MIN_PERIODS})")
        return dataset, resolved, start, end, selected

    def _create_run(self, ctx: AccessContext, dataset: Dataset, data: AnalysisCreate,
                    indicators, period_from: date, period_to: date, selected: tuple[str, ...]) -> AnalysisRun:
        from app.models import Period

        period_from_id = self.session.scalar(
            select(Period.id).where(Period.granularity == dataset.granularity, Period.start_date == period_from)
        )
        period_to_id = self.session.scalar(
            select(Period.id).where(Period.granularity == dataset.granularity, Period.start_date == period_to)
        )
        run = AnalysisRun(
            dataset_id=dataset.id, created_by=ctx.user_id, parent_run_id=data.parent_run_id,
            period_from_id=period_from_id, period_to_id=period_to_id,
            status=AnalysisStatus.QUEUED, random_state=data.random_state,
        )
        self.analyses.add_run(run)
        for indicator, weight in indicators:
            run.indicators.append(AnalysisRunIndicator(indicator_id=indicator.id, weight=weight))
        for ml_name in selected:
            mapping = ML_TO_DB.get(ml_name)
            if mapping is None:
                raise ValidationFailedError(f"Неизвестная процедура: {ml_name}")
            procedure_type, method = mapping
            procedure = AnalysisProcedure(
                procedure_type=procedure_type, method=method, status=ProcedureStatus.PENDING,
            )
            self._store_params(procedure, ml_name, data)
            run.procedures.append(procedure)
        self.session.flush()
        return run

    def _store_params(self, procedure: AnalysisProcedure, ml_name: str, data: AnalysisCreate) -> None:
        if ml_name == "anomalies":
            params = data.anomalies or AnomalyParams()
            add_parameter(procedure, "method", text=params.method)
            add_parameter(procedure, "threshold", numeric=Decimal(str(params.threshold)))
            add_parameter(procedure, "min_observations", numeric=Decimal(params.min_observations))
        elif ml_name == "correlation":
            params = data.correlation or CorrelationParams()
            add_parameter(procedure, "method", text=params.method)
            add_parameter(procedure, "min_observations", numeric=Decimal(params.min_observations))
        elif ml_name == "clustering":
            params = data.clustering or ClusteringParams()
            if isinstance(params.k, int):
                add_parameter(procedure, "k", numeric=Decimal(params.k))
            else:
                add_parameter(procedure, "k", text=str(params.k))
            add_parameter(procedure, "k_min", numeric=Decimal(params.k_min))
            add_parameter(procedure, "k_max", numeric=Decimal(params.k_max))
        elif ml_name == "forecast":
            params = data.forecast or ForecastParams()
            add_parameter(procedure, "horizon", numeric=Decimal(params.horizon))
            add_parameter(procedure, "model", text=params.model)

    def _execute(self, run: AnalysisRun, dataset: Dataset, indicators, period_from: date, period_to: date,
                 selected: tuple[str, ...], data: AnalysisCreate) -> None:
        now = datetime.now(UTC)
        run.status = AnalysisStatus.RUNNING
        run.started_at = now
        for procedure in run.procedures:
            procedure.started_at = now
        self.session.flush()
        payload, code_map, period_ids = self._payload(run, dataset, indicators, period_from, period_to, selected, data)
        try:
            if len(selected) == 1:
                envelope = self.client.run_procedure(selected[0], payload)
                response = AnalyzeResponse(service_version=None, procedures={selected[0]: envelope})
            else:
                response = self.client.analyze(payload)
        except AnalyticsServiceError as exc:
            logger.warning("Исследование %s: сбой аналитического сервиса", run.id)
            run.status = AnalysisStatus.FAILED
            run.error_message = exc.message
            run.finished_at = datetime.now(UTC)
            for procedure in run.procedures:
                if procedure.status == ProcedureStatus.PENDING:
                    procedure.status = ProcedureStatus.ERROR
                    procedure.message = exc.message
                    procedure.finished_at = run.finished_at
            return
        run.analytics_service_version = response.service_version
        persist_procedures(self.session, run, response.procedures, code_map, period_ids, dataset.granularity)
        self.session.flush()
        from app.services.governance_service import GovernanceService
        GovernanceService(self.session).post_process_run(run, dataset, response.procedures, code_map)
        statuses = [p.status for p in run.procedures]
        run.finished_at = datetime.now(UTC)
        if statuses and all(s == ProcedureStatus.ERROR for s in statuses):
            run.status = AnalysisStatus.FAILED
            run.error_message = "Ни одна процедура не выполнена"
        elif any(s == ProcedureStatus.ERROR for s in statuses) or any(s == ProcedureStatus.SKIPPED for s in statuses):
            if any(s == ProcedureStatus.OK for s in statuses) and any(s == ProcedureStatus.ERROR for s in statuses):
                run.status = AnalysisStatus.PARTIALLY_COMPLETED
            elif all(s in {ProcedureStatus.OK, ProcedureStatus.SKIPPED} for s in statuses):
                run.status = AnalysisStatus.COMPLETED if any(s == ProcedureStatus.OK for s in statuses) else AnalysisStatus.FAILED
                if run.status == AnalysisStatus.FAILED:
                    run.error_message = "Недостаточно данных для выбранных процедур"
            else:
                run.status = AnalysisStatus.PARTIALLY_COMPLETED
        else:
            run.status = AnalysisStatus.COMPLETED

    def _payload(self, run, dataset, indicators, period_from, period_to, selected, data) -> tuple[dict, dict, dict]:
        ids = [indicator.id for indicator, _ in indicators]
        rows = self.analyses.matrix_rows(dataset.id, ids, period_from, period_to)
        starts = sorted({row["start_date"] for row in rows})
        if len(starts) < MIN_PERIODS:
            raise ValidationFailedError(
                f"Недостаточно периодов для анализа (нужно не менее {MIN_PERIODS})",
            )
        labels = [format_period(start, dataset.granularity) for start in starts]
        period_ids = {format_period(row["start_date"], dataset.granularity): row["period_id"] for row in rows}
        by_indicator = defaultdict(dict)
        for row in rows:
            by_indicator[row["indicator_id"]][row["start_date"]] = None if row["value"] is None else float(row["value"])
        org = self.session.get(Organization, dataset.organization_id)
        bounds = self.analyses.thresholds(org.id, ids)
        series = []
        code_map = {}
        for indicator, weight in indicators:
            code_map[indicator.code] = indicator
            values = [by_indicator[indicator.id].get(start) for start in starts]
            item = {
                "code": indicator.code,
                "values": values,
                "impact_direction": indicator.impact_direction.value,
                "weight": float(weight),
            }
            low, high = bounds.get(indicator.id, (None, None))
            if low is not None:
                item["lower_bound"] = float(low)
            if high is not None:
                item["upper_bound"] = float(high)
            series.append(item)
        payload = {
            "request_id": str(run.id),
            "random_state": run.random_state,
            "periods": labels,
            "indicators": series,
            "procedures": list(selected),
        }
        payload["anomalies"] = (data.anomalies or AnomalyParams()).model_dump()
        payload["correlation"] = (data.correlation or CorrelationParams()).model_dump()
        payload["clustering"] = (data.clustering or ClusteringParams()).model_dump()
        payload["forecast"] = (data.forecast or ForecastParams()).model_dump()
        return payload, code_map, period_ids


def build_conclusion(run, assessment, anomalies, correlation, clustering, forecast) -> AnalysisConclusion:
    highlights: list[str] = []
    limitations: list[str] = [
        ASSESSMENT_DISCLAIMER,
        "Корреляция — совместное движение рядов.",
        "Номер кластера не означает «кризис» или «норму».",
        "Прогноз — экстраполяция ряда.",
    ]
    if run.status.value == "failed":
        summary = run.error_message or "Исследование не выполнено. Результаты для интерпретации отсутствуют."
        return AnalysisConclusion(summary=summary, highlights=[], limitations=limitations)

    if assessment and assessment.score is not None:
        zone = assessment.interpretation or interpret_score(assessment.score) or "Рассчитано"
        org = getattr(run, "organization_name", None)
        org_bit = f"организации «{org}», " if org else ""
        summary = (
            f"Сводная оценка {float(assessment.score):.0f} из 100 ({zone}) "
            f"за период {run.period_from} — {run.period_to} по {org_bit}набору «{run.dataset_name}»."
        )
        weakest = sorted(
            assessment.components or [],
            key=lambda item: float(item.normalized_score),
        )[:3]
        strongest = sorted(
            assessment.components or [],
            key=lambda item: float(item.normalized_score),
            reverse=True,
        )[:2]
        if weakest:
            names = ", ".join(item.indicator_name for item in weakest)
            highlights.append(f"Ниже относительно собственного диапазона: {names}.")
        if strongest:
            names = ", ".join(item.indicator_name for item in strongest)
            highlights.append(f"Ближе к благоприятной стороне собственного диапазона: {names}.")
    else:
        reason = (assessment.message if assessment else None) or "процедура не входила в запуск или данных недостаточно"
        summary = f"Сводная оценка не рассчитана ({reason}). Ниже — доступные результаты отдельных процедур."
        limitations.append("Без сводного балла сравнивать состояние организации по одной шкале нельзя.")

    if anomalies:
        if anomalies.status.value == "ok" and anomalies.items:
            examples = anomalies.items[:5]
            bits = [
                f"«{item.indicator_name}» в {item.period_start} "
                f"({('выше' if item.direction == 'above' else 'ниже')} типичного уровня)"
                for item in examples
            ]
            highlights.append(
                f"Выбросов: {len(anomalies.items)}. Примеры: {'; '.join(bits)}."
            )
        elif anomalies.status.value == "skipped":
            limitations.append(anomalies.message or "Поиск аномалий пропущен: недостаточно наблюдений.")
        elif anomalies.status.value == "error":
            limitations.append(anomalies.message or "Поиск аномалий завершился ошибкой.")

    if correlation and correlation.status.value == "ok":
        strong = [
            pair for pair in (correlation.pairs or [])
            if pair.coefficient is not None and abs(pair.coefficient) >= 0.7
        ]
        strong.sort(key=lambda pair: abs(pair.coefficient or 0), reverse=True)
        if strong:
            pair = strong[0]
            direction = "прямая" if pair.coefficient > 0 else "обратная"
            highlights.append(
                f"Наиболее выраженная статистическая связь ({direction}, коэффициент "
                f"{pair.coefficient:.2f}): {pair.indicator_a} и {pair.indicator_b}. "
                "Это не доказательство, что один показатель вызывает другой."
            )
        else:
            highlights.append("Сильных попарных корреляций (|r| ≥ 0,7) в выбранном интервале нет.")
    elif correlation and correlation.status.value in {"skipped", "error"}:
        limitations.append(correlation.message or "Корреляции не рассчитаны.")

    if clustering and clustering.status.value == "ok" and clustering.clusters:
        sizes = ", ".join(
            f"группа {item.cluster}: {item.size} наблюдений"
            for item in clustering.clusters
        )
        highlights.append(
            f"Периоды разделены на {len(clustering.clusters)} группы по сходству сочетания показателей ({sizes}). "
            "Сравнивайте центры групп, не присваивая номерам смысл «кризис / норма»."
        )
    elif clustering and clustering.status.value in {"skipped", "error"}:
        limitations.append(clustering.message or "Кластеризация не выполнена.")

    if forecast and forecast.status.value == "ok" and forecast.series:
        series = forecast.series[0]
        if series.points:
            first = series.points[0]
            last = series.points[-1]
            trend = "существенных изменений внутри горизонта не видно"
            if last.value > first.value:
                trend = "точечный прогноз направлен выше последнего рассчитанного шага"
            elif last.value < first.value:
                trend = "точечный прогноз направлен ниже последнего рассчитанного шага"
            highlights.append(
                f"Прогноз по показателю {series.indicator}: горизонт {len(series.points)} шаг(ов); {trend}."
            )
    elif forecast and forecast.status.value in {"skipped", "error"}:
        limitations.append(forecast.message or "Прогноз не построен.")

    skipped = [
        item.message for item in (run.procedures or [])
        if item.status.value == "skipped" and item.message
    ]
    for message in skipped[:4]:
        if message not in limitations:
            limitations.append(message)

    return AnalysisConclusion(summary=summary, highlights=highlights, limitations=limitations)
