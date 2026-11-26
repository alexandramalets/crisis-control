"""Сводка главной панели. Оценка C не пересчитывается: берётся сохранённый результат исследования."""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AnalysisAlert, AnalysisFinding, CrisisMeasure, Organization, Recommendation
from app.models.enums import AnalysisStatus, ImpactDirection, PeriodGranularity, ProcedureStatus, ProcedureType
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.dataset_repository import DatasetRepository
from app.schemas.dashboard import (
    AssessmentFactor, AssessmentGroup, DashboardAnomaly, DashboardAssessment, DashboardCorrelationPair,
    DashboardCorrelations, DashboardPeriod, DashboardRef, DashboardResponse, DashboardRun, IndicatorSeries,
    MetricCardData, OrganizationSnapshot, SeriesPoint,
)
from app.services.access import AccessContext
from app.services.analysis_service import AnalysisService, format_period
from app.services.assessment_labels import interpret_score
from app.services.dataset_service import DatasetService
from app.services.organization_service import OrganizationService

KPI_CODES = ("revenue", "profit", "receivables", "payables", "cash")
KPI_FALLBACK_NAMES = {
    "revenue": "Выручка",
    "profit": "Прибыль",
    "receivables": "Дебиторская задолженность",
    "payables": "Кредиторская задолженность",
    "cash": "Денежные средства",
}
EMPTY_UPLOAD = (
    "Нет доступных наборов данных. Загрузите демонстрационный или собственный набор в разделе «Данные»."
)


def add_months(start: date, delta: int) -> date:
    month = start.month - 1 + delta
    year = start.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


class DashboardService:
    def __init__(self, session: Session):
        self.session = session
        self.datasets = DatasetRepository(session)
        self.analyses = AnalysisRepository(session)

    def build(self, ctx: AccessContext, organization_id: int | None, dataset_id: int | None,
              months: int) -> DashboardResponse:
        ctx.ensure_analyst()
        months = 12 if months not in {3, 6, 12} else months
        snapshots = self._snapshots(ctx)
        if organization_id is None and snapshots:
            organization_id = snapshots[0].id
        if organization_id is not None:
            OrganizationService(self.session).get_visible(ctx, organization_id)
        dataset = self._dataset(ctx, organization_id, dataset_id)
        if dataset is None:
            return DashboardResponse(
                empty=True, message=EMPTY_UPLOAD, cards=[], series=[], anomalies=[], recent_runs=[],
                organization_snapshots=snapshots,
                organization=DashboardRef(id=organization_id, name=next(
                    (item.name for item in snapshots if item.id == organization_id), "Организация",
                )) if organization_id else None,
            )
        organization = self.session.get(Organization, dataset.organization_id)
        period_from, period_to, _ = self.datasets.period_range(dataset.id)
        org_ref = DashboardRef(id=organization.id, name=organization.name)
        set_ref = DashboardRef(id=dataset.id, name=dataset.name)
        if period_from is None or period_to is None:
            return DashboardResponse(
                empty=True,
                message="В наборе нет периодов наблюдения. Загрузите файл с временным рядом.",
                organization=org_ref, dataset=set_ref, granularity=dataset.granularity,
                cards=[], series=[], anomalies=[], recent_runs=[],
                organization_snapshots=snapshots,
            )
        window_start = self._window_start(period_to, months, dataset.granularity)
        if window_start < period_from:
            window_start = period_from

        catalog = self._catalog(dataset.id)
        indicator_ids = [meta["id"] for meta in catalog.values()]
        rows = self.analyses.matrix_rows(dataset.id, indicator_ids, window_start, period_to) if indicator_ids else []
        by_code = self._index_rows(rows, catalog)
        cards = [self._card(code, catalog, by_code.get(code, []), dataset.granularity) for code in KPI_CODES]

        run_id = self._latest_run_id(ctx, dataset.id)
        forecast_by_code: dict[str, list[SeriesPoint]] = {}
        assessment = None
        anomalies: list[DashboardAnomaly] = []
        correlations = None
        if run_id is not None:
            analysis = AnalysisService(self.session)
            forecast_by_code = self._forecasts(analysis, ctx, run_id, dataset.granularity)
            assessment = self._assessment(analysis, ctx, run_id, catalog)
            anomalies = self._anomalies(analysis, ctx, run_id)
            correlations = self._correlations(analysis, ctx, run_id, catalog)

        series = []
        seen = set()
        ordered = list(KPI_CODES) + [code for code in catalog if code not in KPI_CODES]
        for code in ordered:
            if code in seen or code not in catalog:
                continue
            seen.add(code)
            history = [
                SeriesPoint(
                    period_start=start, label=format_period(start, dataset.granularity),
                    value=None if value is None else float(value), kind="history",
                )
                for start, value in by_code.get(code, [])
            ]
            forecast = forecast_by_code.get(code, [])
            if not history and not forecast:
                continue
            series.append(IndicatorSeries(code=code, name=catalog[code]["name"], history=history, forecast=forecast))

        return DashboardResponse(
            empty=False,
            organization=org_ref,
            dataset=set_ref,
            granularity=dataset.granularity,
            period=DashboardPeriod(start=window_start, end=period_to, months=months),
            analysis_run_id=run_id,
            cards=cards,
            series=series,
            assessment=assessment,
            anomalies=anomalies,
            correlations=correlations,
            recent_runs=self._recent_runs(ctx, dataset.id),
            organization_snapshots=snapshots,
            **self._management(dataset.organization_id, run_id, dataset.quality_status),
        )

    def _dataset(self, ctx: AccessContext, organization_id: int | None, dataset_id: int | None):
        if dataset_id is not None:
            dataset = DatasetService(self.session).get_visible(ctx, dataset_id)
            if organization_id is not None and dataset.organization_id != organization_id:
                return None
            return dataset
        if organization_id is None:
            return None
        items, _ = self.datasets.find(ctx.read_scope, organization_id, 1, 0)
        return items[0] if items else None

    def _snapshots(self, ctx: AccessContext) -> list[OrganizationSnapshot]:
        page = OrganizationService(self.session).search(ctx, 50, 0)
        snapshots = []
        for organization in page.items:
            items, _ = self.datasets.find(ctx.read_scope, organization.id, 1, 0)
            dataset = items[0] if items else None
            run_id = None
            for status in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIALLY_COMPLETED):
                rows, _ = self.analyses.find(ctx.read_scope, None, organization.id, status, 1, 0)
                if rows:
                    run_id = rows[0]["id"]
                    break
            score = interpretation = last_at = None
            if run_id is not None:
                analysis = AnalysisService(self.session)
                if self.analyses.procedure(run_id, ProcedureType.ASSESSMENT) is not None:
                    assessment = analysis.assessment(ctx, run_id)
                    score = assessment.score
                    interpretation = assessment.interpretation
                summary = self.analyses.get_summary(run_id, ctx.read_scope)
                last_at = summary.get("finished_at") or summary.get("created_at") if summary else None
            snapshots.append(OrganizationSnapshot(
                id=organization.id,
                name=organization.name,
                dataset_name=dataset.name if dataset is not None else None,
                analysis_run_id=run_id,
                score=score,
                interpretation=interpretation,
                last_analysis_at=last_at,
            ))
        return snapshots

    def _window_start(self, end: date, months: int, granularity: PeriodGranularity) -> date:
        if granularity == PeriodGranularity.MONTH:
            return add_months(end, -(months - 1))
        if granularity == PeriodGranularity.QUARTER:
            steps = max(months // 3, 1)
            return add_months(end, -3 * (steps - 1))
        years = max(months // 12, 1)
        return date(end.year - (years - 1), 1, 1)

    def _catalog(self, dataset_id: int) -> dict[str, dict]:
        catalog = {}
        for indicator in self.analyses.dataset_indicators(dataset_id):
            catalog[indicator.code] = {
                "id": indicator.id,
                "name": indicator.name,
                "unit": indicator.unit.symbol,
                "direction": indicator.impact_direction,
                "group_code": indicator.group.code,
                "group_name": indicator.group.name,
            }
        return catalog

    def _index_rows(self, rows, catalog):
        id_to_code = {meta["id"]: code for code, meta in catalog.items()}
        grouped = defaultdict(list)
        for row in rows:
            code = id_to_code.get(row["indicator_id"])
            if code is None:
                continue
            grouped[code].append((row["start_date"], row["value"]))
        for code in grouped:
            grouped[code].sort(key=lambda item: item[0])
        return grouped

    def _card(self, code, catalog, points, granularity) -> MetricCardData:
        meta = catalog.get(code)
        if meta is None:
            return MetricCardData(
                code=code, name=KPI_FALLBACK_NAMES.get(code, code), unit="руб.",
                impact_direction=ImpactDirection.HIGHER_IS_BETTER, sparkline=[],
            )
        finite = [(start, value) for start, value in points if value is not None]
        current = finite[-1][1] if finite else None
        previous = finite[-2][1] if len(finite) >= 2 else None
        change_percent = change_direction = change_favorable = None
        if current is not None and previous not in (None, 0):
            delta = float(current) - float(previous)
            change_percent = round(100.0 * delta / abs(float(previous)), 1)
            if delta > 0:
                change_direction = "up"
            elif delta < 0:
                change_direction = "down"
            if change_direction:
                if meta["direction"] == ImpactDirection.LOWER_IS_BETTER:
                    change_favorable = delta < 0
                elif meta["direction"] == ImpactDirection.HIGHER_IS_BETTER:
                    change_favorable = delta > 0
        sparkline = []
        if len(finite) >= 3:
            sparkline = [
                SeriesPoint(
                    period_start=start, label=format_period(start, granularity),
                    value=None if value is None else float(value), kind="history",
                )
                for start, value in points[-12:]
            ]
        return MetricCardData(
            code=code, name=meta["name"], unit=meta["unit"], impact_direction=meta["direction"],
            value=current, previous_value=previous, change_percent=change_percent,
            change_direction=change_direction, change_favorable=change_favorable, sparkline=sparkline,
        )

    def _management(self, organization_id: int, run_id: int | None, quality_status: str | None) -> dict:
        alerts = self.session.scalar(
            select(func.count()).select_from(AnalysisAlert).where(AnalysisAlert.organization_id == organization_id)
        ) or 0
        findings = self.session.scalar(
            select(func.count()).select_from(AnalysisFinding).where(AnalysisFinding.organization_id == organization_id)
        ) or 0
        open_measures = self.session.scalar(
            select(func.count()).select_from(CrisisMeasure).where(
                CrisisMeasure.organization_id == organization_id,
                CrisisMeasure.status.in_(("planned", "in_progress", "overdue")),
            )
        ) or 0
        overdue = self.session.scalar(
            select(func.count()).select_from(CrisisMeasure).where(
                CrisisMeasure.organization_id == organization_id, CrisisMeasure.status == "overdue",
            )
        ) or 0
        recs = self.session.scalar(
            select(func.count()).select_from(Recommendation).where(
                Recommendation.organization_id == organization_id, Recommendation.status == "proposed",
            )
        ) or 0
        critical = 0
        if run_id:
            critical = self.session.scalar(
                select(func.count()).select_from(AnalysisAlert).where(
                    AnalysisAlert.run_id == run_id, AnalysisAlert.level.in_(("high", "critical")),
                )
            ) or 0
        if quality_status and quality_status not in {"ready", "ok"}:
            state = "unverified"
        elif run_id is None:
            state = "data_only"
        elif critical:
            state = "problems"
        else:
            state = "ok"
        return {
            "alerts_count": int(alerts),
            "findings_count": int(findings),
            "open_measures": int(open_measures),
            "overdue_measures": int(overdue),
            "proposed_recommendations": int(recs),
            "workspace_state": state,
        }

    def _latest_run_id(self, ctx: AccessContext, dataset_id: int) -> int | None:
        for status in (AnalysisStatus.COMPLETED, AnalysisStatus.PARTIALLY_COMPLETED):
            rows, _ = self.analyses.find(ctx.read_scope, dataset_id, None, status, 1, 0)
            if rows:
                return rows[0]["id"]
        return None

    def _forecasts(self, analysis: AnalysisService, ctx, run_id, granularity) -> dict[str, list[SeriesPoint]]:
        if self.analyses.procedure(run_id, ProcedureType.FORECASTING) is None:
            return {}
        result = analysis.forecasts(ctx, run_id)
        if result.status != ProcedureStatus.OK:
            return {}
        mapped = {}
        for item in result.series:
            mapped[item.indicator] = [
                SeriesPoint(
                    period_start=point.period_start,
                    label=format_period(point.period_start, granularity),
                    value=float(point.value),
                    lower=None if point.lower_bound is None else float(point.lower_bound),
                    upper=None if point.upper_bound is None else float(point.upper_bound),
                    kind="forecast",
                )
                for point in item.points
            ]
        return mapped

    def _assessment(self, analysis: AnalysisService, ctx, run_id, catalog) -> DashboardAssessment | None:
        if self.analyses.procedure(run_id, ProcedureType.ASSESSMENT) is None:
            return None
        stored = analysis.assessment(ctx, run_id)
        if stored.status != ProcedureStatus.OK or stored.score is None:
            return DashboardAssessment(
                status=stored.status, warning=stored.message or "Недостаточно данных",
                groups=[], factors=[],
            )
        grouped = defaultdict(list)
        for item in stored.components:
            meta = catalog.get(item.indicator)
            if meta is None:
                continue
            grouped[(meta["group_code"], meta["group_name"])].append(float(item.normalized_score))
        groups = [
            AssessmentGroup(code=code, name=name, score=round(100 * sum(values) / len(values), 1))
            for (code, name), values in grouped.items() if values
        ]
        groups.sort(key=lambda item: item.name)
        ranked = sorted(stored.components, key=lambda item: item.normalized_score)
        factors = [
            AssessmentFactor(
                code=item.indicator, name=item.indicator_name,
                normalized_score=item.normalized_score, explanation=item.explanation,
            )
            for item in ranked[:3]
        ]
        return DashboardAssessment(
            status=ProcedureStatus.OK, score=stored.score,
            history_score=stored.history_score, compliance_score=stored.compliance_score,
            completeness=stored.completeness,
            interpretation=interpret_score(stored.score),
            groups=groups, factors=factors,
        )

    def _anomalies(self, analysis: AnalysisService, ctx, run_id) -> list[DashboardAnomaly]:
        if self.analyses.procedure(run_id, ProcedureType.ANOMALIES) is None:
            return []
        result = analysis.anomalies(ctx, run_id)
        if result.status != ProcedureStatus.OK:
            return []
        return [
            DashboardAnomaly(
                indicator=item.indicator, indicator_name=item.indicator_name,
                period_start=item.period_start, value=item.value, baseline=item.baseline,
                deviation=item.deviation, score=item.score, direction=item.direction,
                lower_bound=item.lower_bound, upper_bound=item.upper_bound,
            )
            for item in result.items[:20]
        ]

    def _correlations(self, analysis: AnalysisService, ctx, run_id, catalog):
        if self.analyses.procedure(run_id, ProcedureType.CORRELATION) is None:
            return None
        result = analysis.correlations(ctx, run_id)
        if result.status != ProcedureStatus.OK:
            return None
        codes = []
        pairs = []
        for item in result.pairs:
            pairs.append(DashboardCorrelationPair(
                indicator_a=item.indicator_a, indicator_b=item.indicator_b,
                coefficient=item.coefficient, n_observations=item.n_observations,
            ))
            for code in (item.indicator_a, item.indicator_b):
                if code not in codes:
                    codes.append(code)
        names = {code: catalog.get(code, {}).get("name", code) for code in codes}
        return DashboardCorrelations(
            indicators=codes, names=names, pairs=pairs, interpretation=result.interpretation,
        )

    def _recent_runs(self, ctx, dataset_id) -> list[DashboardRun]:
        rows, _ = self.analyses.find(ctx.read_scope, dataset_id, None, None, 5, 0)
        return [
            DashboardRun(
                id=row["id"], dataset_id=row["dataset_id"], dataset_name=row["dataset_name"],
                status=row["status"], created_at=row["created_at"], finished_at=row["finished_at"],
            )
            for row in rows
        ]
