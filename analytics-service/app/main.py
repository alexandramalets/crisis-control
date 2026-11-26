from fastapi import FastAPI

from app import __version__
from app.api.v1.routes import router
from app.core.errors import register_error_handlers

DESCRIPTION = """
Аналитический микросервис. Отдельный процесс без доступа к PostgreSQL.
Вызывается серверным приложением с заголовком `X-Service-Key`.
"""

OPENAPI_TAGS = [
    {"name": "Состояние", "description": "Работоспособность и версии библиотек"},
    {"name": "Методы", "description": "Описание доступных процедур"},
    {"name": "Проверка", "description": "Контроль входной матрицы наблюдений"},
    {"name": "Аномалии", "description": "Медиана и MAD"},
    {"name": "Корреляции", "description": "Пирсон"},
    {"name": "Кластеризация", "description": "k-средних"},
    {"name": "Прогноз", "description": "Экспоненциальное сглаживание"},
    {"name": "Оценка", "description": "Сводный балл 0–100"},
    {"name": "Конвейер", "description": "Несколько процедур за один запрос"},
]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Кризисная аналитика — интеллектуальный микросервис",
        description=DESCRIPTION,
        version=__version__,
        docs_url="/analytics/docs",
        redoc_url=None,
        openapi_url="/analytics/openapi.json",
        openapi_tags=OPENAPI_TAGS,
    )
    register_error_handlers(app)
    app.include_router(router)
    return app
