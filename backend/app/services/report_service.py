"""Чтение и формирование отчётов. PDF собирается на backend по сохранённым результатам."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models import Report
from app.models.enums import ReportFormat, ReportStatus
from app.repositories.report_repository import ReportRepository
from app.schemas.common import Page
from app.schemas.report import ReportRead
from app.services.access import AccessContext
from app.services.analysis_service import AnalysisService
from app.services.dataset_service import DatasetService
from app.services.errors import ConflictError, NotFoundError
from app.services.ingest.upload_service import UploadService
from app.services.organization_service import OrganizationService
from app.services.pdf_report import build_pdf
from app.core.config import get_settings

NOT_FOUND = "Отчёт не найден"


class ReportService:
    def __init__(self, session: Session):
        self.session = session
        self.reports = ReportRepository(session)

    def search(self, ctx: AccessContext, run_id: int | None, limit: int, offset: int) -> Page[ReportRead]:
        ctx.ensure_analyst()
        if run_id is not None:
            AnalysisService(self.session).ensure_visible(ctx, run_id)
        items, total = self.reports.find(ctx.read_scope, run_id, limit, offset)
        return Page(items=[ReportRead.model_validate(r) for r in items], total=total, limit=limit, offset=offset)

    def get(self, ctx: AccessContext, report_id: int, with_content: bool = False) -> Report:
        ctx.ensure_analyst()
        report = self.reports.get(report_id, ctx.read_scope, with_content)
        if report is None:
            raise NotFoundError(NOT_FOUND)
        return report

    def content(self, ctx: AccessContext, report_id: int) -> Report:
        report = self.get(ctx, report_id, with_content=True)
        if report.status != ReportStatus.READY:
            raise ConflictError("Отчёт ещё не сформирован" if report.status == ReportStatus.PENDING
                                else "Отчёт не удалось сформировать", code="report_not_ready")
        return report

    def generate_pdf(self, ctx: AccessContext, run_id: int) -> Report:
        analysis = AnalysisService(self.session)
        results = analysis.results(ctx, run_id)
        dataset = DatasetService(self.session).get_visible(ctx, results.run.dataset_id)
        organization = OrganizationService(self.session).get_visible(ctx, dataset.organization_id)
        quality = None
        try:
            quality = UploadService(self.session, get_settings()).quality(ctx, dataset.id)
        except Exception:
            quality = None
        payload = build_pdf(
            results,
            organization_name=organization.name,
            dataset_name=dataset.name,
            quality=quality,
        )
        report = self.reports.add(Report(
            run_id=run_id,
            created_by=ctx.user_id,
            title=f"Исследование {run_id}: {dataset.name}",
            format=ReportFormat.PDF,
            status=ReportStatus.READY,
            generated_at=datetime.now(UTC),
            content=payload,
        ))
        self.session.commit()
        return report
