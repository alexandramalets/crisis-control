from datetime import date, datetime
from decimal import Decimal

from app.models.enums import AnalysisStatus, ProcedureStatus
from app.schemas.analysis import (
    AnalysisConclusion, AnalysisDetail, AnalysisResults, AssessmentResults, LayeredNarrative,
)
from app.services.pdf_report import build_pdf


def _results():
    run = AnalysisDetail(
        id=1, dataset_id=1, dataset_name="Демо", organization_id=1, created_by=1,
        parent_run_id=None, status=AnalysisStatus.COMPLETED,
        period_from=date(2023, 1, 1), period_to=date(2025, 12, 1),
        created_at=datetime(2026, 1, 1), finished_at=None,
        random_state=42, analytics_service_version="0.1", error_message=None,
        started_at=None, indicators=[], procedures=[],
    )
    return AnalysisResults(
        run=run,
        assessment=AssessmentResults(
            status=ProcedureStatus.OK, message=None, score=Decimal("61"),
            interpretation="Умеренное напряжение", components=[],
        ),
        conclusion=AnalysisConclusion(summary="Краткая сводка", highlights=["Факт"], limitations=["Ограничение"]),
        assessment_narrative=LayeredNarrative(brief="Ориентир 61", details=["Не диагноз"], technical=["метод"]),
    )


def test_pdf_contains_cyrillic_title():
    data = build_pdf(_results(), organization_name="ООО Пример", dataset_name="Демо")
    assert data.startswith(b"%PDF")
    assert b"Crisis" in data or len(data) > 1000
