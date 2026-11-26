from typing import Annotated

from fastapi import APIRouter, Query, Response

from app.api.deps import Access, DbSession, Pagination, error_responses
from app.models.enums import AnalysisStatus
from app.schemas.analysis import (
    AnalysisCreate, AnalysisDetail, AnalysisResults, AnalysisSummary, AnomalyResults, AssessmentResults,
    ClusterResults, CorrelationResults, ForecastResults,
)
from app.schemas.report import ReportRead
from app.services.report_service import ReportService
from app.schemas.common import Page
from app.services.analysis_service import AnalysisService

router = APIRouter(prefix="/analyses", tags=["Аналитические исследования"], responses=error_responses(401))
WRITE_ERRORS = error_responses(403, 404, 422, 502, 503)


@router.get("", response_model=Page[AnalysisSummary], summary="История исследований",
            responses=error_responses(404, 422))
def list_analyses(
    access: Access, db: DbSession, page: Pagination,
    dataset_id: Annotated[int | None, Query()] = None,
    organization_id: Annotated[int | None, Query()] = None,
    status: Annotated[AnalysisStatus | None, Query()] = None,
):
    return AnalysisService(db).search(access, dataset_id, organization_id, status, page.limit, page.offset)


@router.get("/methods", summary="Доступные методы аналитического сервиса",
            responses=error_responses(503))
def analysis_methods(access: Access, db: DbSession):
    return AnalysisService(db).methods(access)


@router.post("", response_model=AnalysisDetail, summary="Комплексный анализ",
             responses=WRITE_ERRORS)
def start_analysis(body: AnalysisCreate, access: Access, db: DbSession):
    return AnalysisService(db).start(access, body)


@router.post("/anomalies", response_model=AnalysisDetail, summary="Обнаружение аномалий",
             responses=WRITE_ERRORS)
def start_anomalies(body: AnalysisCreate, access: Access, db: DbSession):
    body.procedures = ["anomalies"]
    return AnalysisService(db).start(access, body)


@router.post("/correlation", response_model=AnalysisDetail, summary="Корреляционный анализ",
             responses=WRITE_ERRORS)
def start_correlation(body: AnalysisCreate, access: Access, db: DbSession):
    body.procedures = ["correlation"]
    return AnalysisService(db).start(access, body)


@router.post("/clustering", response_model=AnalysisDetail, summary="Кластеризация",
             responses=WRITE_ERRORS)
def start_clustering(body: AnalysisCreate, access: Access, db: DbSession):
    body.procedures = ["clustering"]
    return AnalysisService(db).start(access, body)


@router.post("/forecast", response_model=AnalysisDetail, summary="Прогнозирование",
             responses=WRITE_ERRORS)
def start_forecast(body: AnalysisCreate, access: Access, db: DbSession):
    body.procedures = ["forecast"]
    return AnalysisService(db).start(access, body)


@router.post("/assessment", response_model=AnalysisDetail, summary="Сводная оценка состояния",
             responses=WRITE_ERRORS)
def start_assessment(body: AnalysisCreate, access: Access, db: DbSession):
    body.procedures = ["assessment"]
    return AnalysisService(db).start(access, body)


@router.get("/{run_id}", response_model=AnalysisDetail,
            summary="Исследование: параметры, статус каждой процедуры", responses=error_responses(404))
def get_analysis(run_id: int, access: Access, db: DbSession):
    return AnalysisService(db).detail(access, run_id)


@router.get("/{run_id}/results", response_model=AnalysisResults, summary="Сводный результат исследования",
            responses=error_responses(404))
def get_results(run_id: int, access: Access, db: DbSession):
    return AnalysisService(db).results(access, run_id)


@router.get("/{run_id}/anomalies", response_model=AnomalyResults, summary="Результаты обнаружения аномалий",
            responses=error_responses(404))
def get_anomalies(run_id: int, access: Access, db: DbSession):
    return AnalysisService(db).anomalies(access, run_id)


@router.get("/{run_id}/correlations", response_model=CorrelationResults, summary="Корреляционная матрица",
            responses=error_responses(404))
def get_correlations(run_id: int, access: Access, db: DbSession):
    return AnalysisService(db).correlations(access, run_id)


@router.get("/{run_id}/clusters", response_model=ClusterResults, summary="Результаты кластеризации",
            responses=error_responses(404))
def get_clusters(run_id: int, access: Access, db: DbSession):
    return AnalysisService(db).clusters(access, run_id)


@router.get("/{run_id}/forecasts", response_model=ForecastResults, summary="Прогнозные ряды",
            responses=error_responses(404))
def get_forecasts(run_id: int, access: Access, db: DbSession):
    return AnalysisService(db).forecasts(access, run_id)


@router.get("/{run_id}/assessment", response_model=AssessmentResults, summary="Сводная оценка",
            responses=error_responses(404))
def get_assessment(run_id: int, access: Access, db: DbSession):
    return AnalysisService(db).assessment(access, run_id)


@router.post("/{run_id}/rerun", response_model=AnalysisDetail, summary="Повторный запуск с теми же или новыми параметрами",
             responses=WRITE_ERRORS)
def rerun_analysis(run_id: int, access: Access, db: DbSession, body: AnalysisCreate | None = None):
    return AnalysisService(db).rerun(access, run_id, body)


@router.delete("/{run_id}", status_code=204, summary="Удаление исследования",
               responses=error_responses(403, 404))
def delete_analysis(run_id: int, access: Access, db: DbSession):
    AnalysisService(db).delete(access, run_id)
    return Response(status_code=204)


@router.post("/{run_id}/report", response_model=ReportRead, summary="Сформировать PDF по исследованию",
             responses=error_responses(403, 404, 422))
def create_analysis_report(run_id: int, access: Access, db: DbSession):
    return ReportRead.model_validate(ReportService(db).generate_pdf(access, run_id))
