from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.api.deps import Access, DbSession, Pagination, error_responses
from app.models.enums import ReportFormat
from app.schemas.common import Page
from app.schemas.report import ReportRead
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["Отчёты"], responses=error_responses(401))

MEDIA_TYPES = {
    ReportFormat.PDF: "application/pdf",
    ReportFormat.XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


@router.post("", response_model=ReportRead, status_code=status.HTTP_201_CREATED,
             summary="Сформировать PDF-отчёт по исследованию", responses=error_responses(403, 404, 422))
def create_report(access: Access, db: DbSession,
                  run_id: Annotated[int, Query(description="Исследование")]):
    report = ReportService(db).generate_pdf(access, run_id)
    return ReportRead.model_validate(report)


@router.get("", response_model=Page[ReportRead], summary="Список отчётов", responses=error_responses(404))
def list_reports(access: Access, db: DbSession, page: Pagination,
                 run_id: Annotated[int | None, Query(description="Фильтр по исследованию")] = None):
    return ReportService(db).search(access, run_id, page.limit, page.offset)


@router.get("/{report_id}", response_model=ReportRead, summary="Сведения об отчёте", responses=error_responses(404))
def get_report(report_id: int, access: Access, db: DbSession):
    return ReportRead.model_validate(ReportService(db).get(access, report_id))


@router.get("/{report_id}/content", summary="Файл отчёта",
            responses={200: {"content": {media: {} for media in MEDIA_TYPES.values()}},
                       **error_responses(404, 409)})
def download_report(report_id: int, access: Access, db: DbSession):
    report = ReportService(db).content(access, report_id)
    filename = f"report-{report.id}.{report.format.value}"
    return Response(content=report.content, media_type=MEDIA_TYPES[report.format],
                    headers={"Content-Disposition": f'attachment; filename="{filename}"',
                             "Cache-Control": "no-store"})
