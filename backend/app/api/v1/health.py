import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app import __version__
from app.core.config import Settings, get_settings
from app.db.migrations import current_revision, head_revision
from app.db.session import database_version, get_engine
from app.integrations import analytics_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["Состояние"])


def schema_revisions() -> tuple[str | None, str]:
    with get_engine().connect() as connection:
        return current_revision(connection), head_revision()


@router.get("", summary="Проверка работоспособности процесса")
def liveness():
    return {"status": "ok", "service": "backend", "version": __version__}


@router.get("/ready", summary="Проверка готовности: БД и аналитический сервис")
def readiness(settings: Settings = Depends(get_settings)):
    components = {}

    try:
        version = database_version()
        current, head = schema_revisions()
        if current == head:
            components["database"] = {"status": "ok", "version": version, "schema_revision": current}
        else:
            components["database"] = {
                "status": "error", "version": version, "schema_revision": current, "expected_revision": head,
                "message": "Схема БД не соответствует версии приложения. Выполните python -m app.db.setup",
            }
    except SQLAlchemyError as exc:
        logger.warning("Проверка БД не пройдена: %s", exc.__class__.__name__)
        components["database"] = {"status": "error", "message": "База данных недоступна"}

    try:
        health = analytics_client.get_health(settings)
        analytics_client.get_capabilities(settings)
        components["analytics"] = {"status": "ok", "version": health.get("version")}
    except analytics_client.AnalyticsServiceError as exc:
        components["analytics"] = {"status": "error", "message": str(exc)}

    ready = (
        components.get("database", {}).get("status") == "ok"
        and components.get("analytics", {}).get("status") == "ok"
    )
    body = {
        "status": "ok" if ready else "degraded",
        "service": "backend",
        "version": __version__,
        "components": components,
    }
    return JSONResponse(status_code=200 if ready else 503, content=body)
