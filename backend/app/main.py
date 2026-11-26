from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import register_error_handlers

DESCRIPTION = """
Серверная часть информационной системы «Кризисная аналитика».

Авторизация: `POST /api/v1/auth/login` возвращает access-токен (передаётся в заголовке
`Authorization: Bearer <токен>`) и устанавливает refresh-токен в httpOnly-cookie.
Ошибки возвращаются в едином формате `{"error": {"code", "message", "details"}}`.
Объекты других пользователей недоступны и возвращают `404`.
"""

OPENAPI_TAGS = [
    {"name": "Состояние", "description": "Проверка работоспособности и готовности"},
    {"name": "Авторизация", "description": "Вход, выход, обновление токена, профиль"},
    {"name": "Организации", "description": "Объекты управления, данные которых анализируются"},
    {"name": "Справочники", "description": "Показатели, единицы измерения"},
    {"name": "Наборы данных", "description": "Многомерные данные о деятельности организации"},
    {"name": "Аналитические исследования", "description": "Запуски анализа и их состояние"},
    {"name": "Отчёты", "description": "Сформированные отчёты по исследованиям"},
]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Кризисная аналитика — серверное приложение",
        description=DESCRIPTION,
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        openapi_tags=OPENAPI_TAGS,
    )
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
            max_age=600,
        )
    register_error_handlers(app)
    app.include_router(api_router)
    return app
