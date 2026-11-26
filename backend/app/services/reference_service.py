from sqlalchemy.orm import Session

from app.repositories.reference_repository import ReferenceRepository
from app.schemas.reference import IndicatorRead
from app.services.access import AccessContext


class ReferenceService:
    def __init__(self, session: Session):
        self.reference = ReferenceRepository(session)

    def indicators(self, ctx: AccessContext) -> list[IndicatorRead]:
        return [IndicatorRead.model_validate(i) for i in self.reference.list_indicators(ctx.user_id)]
