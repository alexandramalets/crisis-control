import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.db.session import describe_connection_error
from app.services.errors import ServiceError

logger = logging.getLogger(__name__)

HTTP_MESSAGES = {
    400: "Некорректный запрос",
    401: "Требуется авторизация",
    403: "Доступ запрещён",
    404: "Ресурс не найден",
    405: "Метод не поддерживается",
    413: "Файл слишком большой",
    422: "Ошибка проверки данных",
    503: "Сервис временно недоступен",
}


VALIDATION_MESSAGES = {
    "missing": "Обязательное поле",
    "string_too_short": "Слишком короткое значение (минимум {min_length} симв.)",
    "string_too_long": "Слишком длинное значение (максимум {max_length} симв.)",
    "string_pattern_mismatch": "Значение не соответствует допустимому формату",
    "string_type": "Ожидается строка",
    "too_short": "Слишком мало элементов (минимум {min_length})",
    "too_long": "Слишком много элементов (максимум {max_length})",
    "int_parsing": "Ожидается целое число",
    "int_type": "Ожидается целое число",
    "greater_than_equal": "Значение должно быть не меньше {ge}",
    "less_than_equal": "Значение должно быть не больше {le}",
    "decimal_parsing": "Ожидается число",
    "decimal_type": "Ожидается число",
    "decimal_max_digits": "Не более {max_digits} значащих цифр",
    "decimal_max_places": "Не более {decimal_places} знаков после запятой",
    "decimal_whole_digits": "Слишком большое число",
    "finite_number": "Ожидается конечное число",
    "date_from_datetime_parsing": "Ожидается дата в формате ГГГГ-ММ-ДД",
    "date_parsing": "Ожидается дата в формате ГГГГ-ММ-ДД",
    "enum": "Допустимые значения: {expected}",
    "bool_parsing": "Ожидается логическое значение",
    "json_invalid": "Некорректный JSON",
    "model_attributes_type": "Ожидается объект",
    "list_type": "Ожидается список",
}


def validation_message(error: dict) -> str:
    """Сообщение об ошибке проверки на русском языке."""
    if error["type"] == "value_error":
        message = str(error.get("ctx", {}).get("error", error["msg"]))
        if "email address" in message:
            return "Некорректный адрес электронной почты"
        return message
    template = VALIDATION_MESSAGES.get(error["type"])
    if template is None:
        return error["msg"]
    try:
        return template.format(**error.get("ctx", {}))
    except (KeyError, IndexError):
        return template


def error_body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException):
        message = exc.detail if isinstance(exc.detail, str) and exc.detail not in ("Not Found", "Method Not Allowed") \
            else HTTP_MESSAGES.get(exc.status_code, "Ошибка запроса")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(f"http_{exc.status_code}", message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(map(str, e["loc"])), "message": validation_message(e)} for e in exc.errors()]
        return JSONResponse(status_code=422, content=error_body("validation_error", HTTP_MESSAGES[422], details))

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError):
        return JSONResponse(status_code=exc.status_code, content=error_body(exc.code, exc.message, exc.details),
                            headers=exc.headers)

    @app.exception_handler(OperationalError)
    async def database_unavailable(_: Request, exc: OperationalError):
        logger.error("БД недоступна: %s", describe_connection_error(exc))
        return JSONResponse(status_code=503, content=error_body("database_unavailable",
                                                                "База данных временно недоступна"))

    @app.exception_handler(IntegrityError)
    async def integrity_error(_: Request, exc: IntegrityError):
        # Сервисы проверяют данные заранее; сюда попадают гонки и нарушения, не выявленные проверками
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        logger.warning("Нарушение ограничения целостности: %s", constraint)
        return JSONResponse(status_code=409, content=error_body(
            "integrity_error", "Операция нарушает ограничения целостности данных", {"constraint": constraint}))

    @app.exception_handler(Exception)
    async def unhandled_error(request: Request, exc: Exception):
        # Текст исключения может содержать данные запроса — в журнал только тип и путь
        logger.error("Необработанная ошибка %s при %s %s", type(exc).__name__, request.method, request.url.path,
                     exc_info=exc)
        return JSONResponse(status_code=500, content=error_body("internal_error", "Внутренняя ошибка сервера"))
