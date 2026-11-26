from fastapi import APIRouter

from app.api.deps import Access, DbSession, error_responses
from app.schemas.reference import IndicatorRead
from app.services.reference_service import ReferenceService

router = APIRouter(prefix="/reference", tags=["Справочники"], responses=error_responses(401))


@router.get("/indicators", response_model=list[IndicatorRead],
            summary="Показатели: системные и созданные пользователем")
def list_indicators(access: Access, db: DbSession):
    return ReferenceService(db).indicators(access)
