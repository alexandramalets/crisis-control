"""Сохранение ответа аналитического сервиса в таблицы результатов. Без пересчёта алгоритмов."""

import logging
from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.integrations.analytics_contracts import ProcedureEnvelope
from app.models import (
    AnalysisParameter, AnalysisProcedure, AnomalyBaseline, AnomalyResult, Assessment, AssessmentComponent,
    Cluster, ClusterCentroid, ClusterMember, CorrelationResult, ForecastPoint, ForecastSeries, Indicator,
    ProcedureMetric, RatioResult, TrendResult,
)
from app.models.enums import ImpactDirection, ProcedureStatus, ProcedureType
from app.repositories.reference_repository import ReferenceRepository
from app.services.ingest.periods import parse_period

logger = logging.getLogger(__name__)

ML_TO_DB = {
    "validate": (ProcedureType.PREPROCESSING, "quality_check"),
    "anomalies": (ProcedureType.ANOMALIES, "robust_z"),
    "correlation": (ProcedureType.CORRELATION, "pearson"),
    "clustering": (ProcedureType.CLUSTERING, "kmeans"),
    "forecast": (ProcedureType.FORECASTING, "simple_exponential_smoothing"),
    "assessment": (ProcedureType.ASSESSMENT, "weighted_normalized"),
    "trends": (ProcedureType.TRENDS, "theil_sen_kendall"),
    "ratios": (ProcedureType.RATIOS, "deterministic_ratios"),
}


def as_amount(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def as_unit(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.00001"), rounding=ROUND_HALF_UP)


def as_score(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def persist_procedures(session: Session, run, envelopes: dict[str, ProcedureEnvelope],
                       code_to_indicator: dict[str, Indicator], period_ids: dict[str, int],
                       granularity) -> None:
    now = datetime.now(UTC)
    for ml_name, envelope in envelopes.items():
        mapping = ML_TO_DB.get(ml_name)
        if mapping is None:
            continue
        procedure_type, default_method = mapping
        procedure = next((p for p in run.procedures if p.procedure_type == procedure_type), None)
        if procedure is None:
            continue
        procedure.status = ProcedureStatus(envelope.status)
        procedure.message = envelope.message
        if envelope.warnings:
            extra = "; ".join(envelope.warnings)
            procedure.message = f"{procedure.message}; {extra}" if procedure.message else extra
        procedure.finished_at = now
        if procedure.started_at is None:
            procedure.started_at = now
        result = envelope.result or {}
        method = result.get("method") or result.get("algorithm") or result.get("method_family") or default_method
        if isinstance(method, str):
            procedure.method = method[:50]
        if envelope.status != "ok" or not result:
            continue
        if ml_name == "anomalies":
            _anomalies(session, procedure, result, code_to_indicator, period_ids)
        elif ml_name == "correlation":
            _correlation(session, procedure, result, code_to_indicator)
        elif ml_name == "clustering":
            _clustering(session, procedure, result, code_to_indicator, period_ids)
        elif ml_name == "forecast":
            _forecast(session, procedure, result, code_to_indicator, period_ids, granularity)
        elif ml_name == "assessment":
            _assessment(session, run, result, code_to_indicator)
        elif ml_name == "trends":
            _trends(session, procedure, result, code_to_indicator)
        elif ml_name == "ratios":
            _ratios(session, run, result)


def add_parameter(procedure: AnalysisProcedure, name: str, *, numeric=None, text=None, boolean=None,
                  position: int = 0) -> None:
    procedure.parameters.append(AnalysisParameter(
        name=name, position=position, numeric_value=numeric, text_value=text, boolean_value=boolean,
    ))


def _anomalies(session, procedure, result, codes, period_ids):
    for baseline in result.get("baselines") or []:
        indicator = codes.get(baseline.get("indicator"))
        if indicator is None:
            continue
        center = as_amount(baseline["center"])
        lower = as_amount(baseline["lower_bound"])
        upper = as_amount(baseline["upper_bound"])
        if lower > center:
            lower = center
        if upper < center:
            upper = center
        session.add(AnomalyBaseline(
            procedure_id=procedure.id, indicator_id=indicator.id,
            center=center, lower_bound=lower, upper_bound=upper,
        ))
    session.flush()
    for item in result.get("anomalies") or []:
        indicator = codes.get(item.get("indicator"))
        period_id = period_ids.get(item.get("period"))
        score = item.get("score")
        if indicator is None or period_id is None or score in (None, 0):
            continue
        session.add(AnomalyResult(
            procedure_id=procedure.id, indicator_id=indicator.id, period_id=period_id, score=float(score),
        ))


def _correlation(session, procedure, result, codes):
    seen = set()
    for pair in result.get("pairs") or []:
        left = codes.get(pair.get("indicator_a"))
        right = codes.get(pair.get("indicator_b"))
        if left is None or right is None or left.id == right.id:
            continue
        a_id, b_id = (left.id, right.id) if left.id < right.id else (right.id, left.id)
        if (a_id, b_id) in seen:
            continue
        seen.add((a_id, b_id))
        session.add(CorrelationResult(
            procedure_id=procedure.id, indicator_a_id=a_id, indicator_b_id=b_id,
            coefficient=pair.get("coefficient"), p_value=pair.get("p_value"),
            n_observations=int(pair.get("n_observations") or 0),
        ))


def _clustering(session, procedure, result, codes, period_ids):
    if result.get("silhouette") is not None:
        session.add(ProcedureMetric(procedure_id=procedure.id, metric_code="silhouette",
                                    value=float(result["silhouette"])))
    if result.get("inertia") is not None:
        session.add(ProcedureMetric(procedure_id=procedure.id, metric_code="inertia",
                                    value=float(result["inertia"])))
    clusters = result.get("clusters") or []
    ranked = _rank_clusters(clusters, codes)
    for item in clusters:
        number = int(item["cluster"])
        session.add(Cluster(
            procedure_id=procedure.id, cluster_number=number, label=ranked.get(number),
        ))
    session.flush()
    for item in clusters:
        number = int(item["cluster"])
        centroid = item.get("centroid") or {}
        for code, value in centroid.items():
            indicator = codes.get(code)
            if indicator is None:
                continue
            session.add(ClusterCentroid(
                procedure_id=procedure.id, cluster_number=number,
                indicator_id=indicator.id, value=as_amount(value),
            ))
    for member in result.get("members") or []:
        period_id = period_ids.get(member.get("period"))
        if period_id is None:
            continue
        session.add(ClusterMember(
            procedure_id=procedure.id, period_id=period_id, cluster_number=int(member["cluster"]),
            pc1=member.get("pc1"), pc2=member.get("pc2"),
        ))


def _rank_clusters(clusters: list[dict], codes: dict[str, Indicator]) -> dict[int, str]:
    """Относительные подписи по направлению влияния. Не использует слово «кризис»."""
    scored = []
    for item in clusters:
        centroid = item.get("centroid") or {}
        parts = []
        for code, value in centroid.items():
            indicator = codes.get(code)
            if indicator is None:
                continue
            numeric = float(value)
            if indicator.impact_direction == ImpactDirection.LOWER_IS_BETTER:
                numeric = -numeric
            elif indicator.impact_direction == ImpactDirection.NEUTRAL:
                continue
            parts.append(numeric)
        score = sum(parts) / len(parts) if parts else 0.0
        scored.append((score, int(item["cluster"])))
    scored.sort(reverse=True)
    labels = {}
    n = len(scored)
    for rank, (_, number) in enumerate(scored):
        if n == 1:
            labels[number] = "одна группа"
        elif rank == 0:
            labels[number] = "выше типичного уровня"
        elif rank == n - 1:
            labels[number] = "ниже типичного уровня"
        else:
            labels[number] = "средний уровень"
    return labels


def _forecast(session, procedure, result, codes, period_ids, granularity):
    reference = ReferenceRepository(session)
    for series in result.get("series") or []:
        indicator = codes.get(series.get("indicator"))
        if indicator is None:
            continue
        session.add(ForecastSeries(
            procedure_id=procedure.id, indicator_id=indicator.id,
            model_name=(series.get("method") or "simple_exponential_smoothing")[:50],
        ))
        session.flush()
        for point in series.get("forecast") or []:
            label = point.get("period")
            period_id = period_ids.get(label)
            if period_id is None and label:
                parsed = parse_period(str(label), granularity)
                if parsed is None:
                    logger.warning("Прогнозный период не распознан")
                    continue
                start, gran = parsed
                created = reference.ensure_periods(gran, {start})
                period_id = created.get(start)
                if period_id:
                    period_ids[label] = period_id
            if period_id is None or point.get("value") is None:
                continue
            value = as_amount(point["value"])
            lower = None if point.get("lower") is None else as_amount(point["lower"])
            upper = None if point.get("upper") is None else as_amount(point["upper"])
            if lower is not None and lower > value:
                lower = value
            if upper is not None and upper < value:
                upper = value
            session.add(ForecastPoint(
                procedure_id=procedure.id, indicator_id=indicator.id, period_id=period_id,
                value=value, lower_bound=lower, upper_bound=upper,
            ))


def _trends(session, procedure, result, codes):
    for item in result.get("items") or []:
        indicator = codes.get(item.get("indicator"))
        if indicator is None or item.get("slope") is None:
            continue
        session.add(TrendResult(
            procedure_id=procedure.id, indicator_id=indicator.id,
            slope=float(item["slope"]), intercept=float(item.get("intercept") or 0),
            kendall_tau=item.get("kendall_tau"), p_value=item.get("p_value"),
            abs_change=item.get("abs_change"), pct_change=item.get("pct_change"),
            consecutive_worsening=item.get("consecutive_worsening"),
            label=item.get("label"), significant=item.get("significant"),
        ))


def _ratios(session, run, result):
    for item in result.get("items") or []:
        if not item.get("code"):
            continue
        session.add(RatioResult(
            run_id=run.id, code=item["code"], name=item.get("name") or item["code"],
            category=item.get("category") or "other", formula=item.get("formula") or "",
            last_value=item.get("last_value"),
            previous_value=item.get("previous_value"), abs_change=item.get("abs_change"),
            pct_change=item.get("pct_change"), payload=item,
        ))


def _assessment(session, run, result, codes):
    score = result.get("score")
    if result.get("status") not in {"ok", "insufficient_data"}:
        return
    if score is None:
        score = result.get("history_score")
    if score is None:
        return
    session.add(Assessment(
        run_id=run.id, score=as_score(score),
        history_score=None if result.get("history_score") is None else as_score(result["history_score"]),
        compliance_score=None if result.get("compliance_score") is None else as_score(result["compliance_score"]),
        completeness=None if result.get("completeness") is None else as_unit(result["completeness"]),
    ))
    session.flush()
    for component in result.get("components") or []:
        indicator = codes.get(component.get("indicator"))
        if indicator is None:
            continue
        session.add(AssessmentComponent(
            run_id=run.id, indicator_id=indicator.id,
            normalized_score=as_unit(component["normalized_score"]),
            explanation=component.get("explanation"),
        ))
