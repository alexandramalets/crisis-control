from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.models.enums import AnalysisStatus, ProcedureStatus
from app.schemas.analysis import (
    AssessmentComponentRead, AssessmentResults, ClusterProfile, ClusterResults, CorrelationItem,
    CorrelationResults,
)
from app.services.analysis_service import build_conclusion


def _run(**kwargs):
    defaults = dict(
        status=AnalysisStatus.COMPLETED,
        error_message=None,
        period_from=date(2024, 1, 1),
        period_to=date(2024, 12, 1),
        dataset_name="Демо",
        procedures=[],
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_conclusion_uses_score_and_disclaimer():
    assessment = AssessmentResults(
        status=ProcedureStatus.OK,
        message="Сводная оценка 80 из 100",
        score=Decimal("80"),
        interpretation="Устойчивое состояние",
        components=[
            AssessmentComponentRead(
                indicator="cash", indicator_name="Денежные средства",
                weight=Decimal("0.5"), normalized_score=Decimal("0.4"),
            ),
            AssessmentComponentRead(
                indicator="revenue", indicator_name="Выручка",
                weight=Decimal("0.5"), normalized_score=Decimal("0.9"),
            ),
        ],
    )
    text = build_conclusion(_run(), assessment, None, None, None, None)
    assert "80" in text.summary
    assert "Устойчивое состояние" in text.summary
    assert any("Денежные средства" in item for item in text.highlights)
    assert any("не диагноз" in item for item in text.limitations)


def test_conclusion_does_not_call_correlation_causality():
    correlation = CorrelationResults(
        status=ProcedureStatus.OK,
        message=None,
        pairs=[
            CorrelationItem(
                indicator_a="revenue", indicator_b="profit",
                coefficient=0.91, p_value=None, n_observations=12,
            ),
        ],
    )
    text = build_conclusion(_run(), None, None, correlation, None, None)
    assert any("не доказательство" in item for item in text.highlights)
    cluster = ClusterResults(
        status=ProcedureStatus.OK, message=None, metrics={},
        clusters=[ClusterProfile(cluster=0, label=None, size=8, centroid={})],
        members=[],
    )
    clustered = build_conclusion(_run(), None, None, None, cluster, None)
    joined = " ".join(clustered.highlights)
    assert "кризис / норма" in joined
    assert "диагноз" not in joined.lower()
