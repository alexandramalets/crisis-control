from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import Access, DbSession, error_responses
from app.schemas.dashboard import DashboardResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(tags=["Главная панель"], responses=error_responses(401))


@router.get("/dashboard", response_model=DashboardResponse, summary="Сводка главной панели",
            responses=error_responses(404, 422))
def get_dashboard(
    access: Access, db: DbSession,
    organization_id: Annotated[int | None, Query()] = None,
    dataset_id: Annotated[int | None, Query()] = None,
    months: Annotated[int, Query(ge=1, le=36)] = 12,
):
    return DashboardService(db).build(access, organization_id, dataset_id, months)
