from datetime import date
from decimal import Decimal

from app.models.enums import ProcedureStatus
from app.schemas.analysis import (
    AnomalyItem, AnomalyResults, AssessmentResults, ClusterProfile, ClusterResults,
    CorrelationItem, CorrelationResults, ForecastPointRead, ForecastResults, ForecastSeriesRead,
)
from app.services.narratives import (
    anomalies_narrative, assessment_narrative, clustering_narrative, correlation_narrative, forecast_narrative,
)


def test_assessment_narrative_has_three_layers():
    text = assessment_narrative(AssessmentResults(
        status=ProcedureStatus.OK, message=None, score=Decimal("42"),
        interpretation="Требует внимания", components=[],
    ))
    assert "42" in text.brief
    assert any("не" in item.lower() or "диагноз" in item.lower() or "ориентир" in item.lower() or "поддерж" in item.lower()
               for item in text.details)
    assert text.technical


def test_correlation_narrative_rejects_causality():
    text = correlation_narrative(CorrelationResults(
        status=ProcedureStatus.OK, message=None,
        pairs=[CorrelationItem(indicator_a="revenue", indicator_b="profit", coefficient=0.91, p_value=None, n_observations=36)],
    ))
    blob = " ".join([text.brief, *text.details])
    assert "причин" not in blob.lower() or "не" in blob.lower()


def test_cluster_narrative_avoids_crisis_labels():
    text = clustering_narrative(ClusterResults(
        status=ProcedureStatus.OK, message=None, metrics={},
        clusters=[ClusterProfile(cluster=0, label=None, size=10, centroid={})],
        members=[],
    ))
    assert "1" in text.brief
    assert any("не означает" in item for item in text.details)


def test_anomaly_and_forecast_narratives():
    anomalies = anomalies_narrative(AnomalyResults(
        status=ProcedureStatus.OK, message=None, items=[
            AnomalyItem(
                indicator="cash", indicator_name="Денежные средства", period_start=date(2024, 6, 1),
                value=Decimal("1"), baseline=Decimal("10"), deviation=Decimal("-9"),
                score=3.2, direction="below", lower_bound=Decimal("2"), upper_bound=Decimal("20"),
            ),
        ], baselines=[],
    ))
    assert "Денежные средства" in anomalies.brief
    forecast = forecast_narrative(ForecastResults(
        status=ProcedureStatus.OK, message=None,
        series=[ForecastSeriesRead(indicator="revenue", method="ets", points=[
            ForecastPointRead(period_start=date(2025, 1, 1), value=Decimal("100"), lower_bound=None, upper_bound=None),
        ])],
    ))
    assert forecast.brief
