import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    status_code = 400
    code = "service_error"

    def __init__(self, message: str, details=None, code: str | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        if code is not None:
            self.code = code
        if self.code == "invalid_data":
            self.status_code = 422


class InsufficientDataError(ServiceError):
    status_code = 422
    code = "insufficient_data"


def error_body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) and exc.status_code != 404 else (
            "Ресурс не найден" if exc.status_code == 404 else str(exc.detail)
        )
        if exc.status_code == 401:
            message = exc.detail if isinstance(exc.detail, str) else "Неверный межсервисный ключ"
        return JSONResponse(status_code=exc.status_code, content=error_body(f"http_{exc.status_code}", message))

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError):
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(map(str, e["loc"])), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content=error_body("validation_error", "Ошибка проверки данных", details))

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        logger.error("Необработанная ошибка %s при %s %s", type(exc).__name__, request.method, request.url.path,
                     exc_info=exc)
        return JSONResponse(status_code=500, content=error_body("internal_error", "Внутренняя ошибка сервиса"))
