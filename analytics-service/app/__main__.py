"""Точка входа: python -m app

Перед запуском HTTP-сервера проверяет конфигурацию, порт и импорт научных библиотек,
чтобы ошибки запуска выводились понятным сообщением.
"""

import importlib
import logging
import socket
import sys

import uvicorn
from pydantic import ValidationError

EXIT_CONFIG_ERROR = 2
EXIT_LIBRARY_ERROR = 3
EXIT_PORT_BUSY = 4

REQUIRED_MODULES = ("pandas", "numpy", "scipy", "sklearn", "statsmodels.api")


def _fail(code: int, message: str) -> None:
    print(f"ОШИБКА ЗАПУСКА: {message}", file=sys.stderr)
    sys.exit(code)


def main() -> None:
    from app.core.config import get_settings

    try:
        settings = get_settings()
    except ValidationError as exc:
        fields = ", ".join(str(e["loc"][0]).upper() for e in exc.errors())
        _fail(EXIT_CONFIG_ERROR, f"некорректная конфигурация, проверьте переменные окружения: {fields}. "
                                 "Образец — в файле .env.example.")

    from app.core.logging import configure_logging

    configure_logging(settings.log_level)

    from app.core.tls import TLSConfigError, deployment_problems, uvicorn_ssl_kwargs

    problems = deployment_problems(settings)
    if problems:
        _fail(EXIT_CONFIG_ERROR, "; ".join(problems))
    try:
        ssl_kwargs = uvicorn_ssl_kwargs(settings.tls_cert_file, settings.tls_key_file)
    except TLSConfigError as exc:
        _fail(EXIT_CONFIG_ERROR, exc.message)

    for module in REQUIRED_MODULES:
        try:
            importlib.import_module(module)
        except ImportError as exc:
            _fail(EXIT_LIBRARY_ERROR, f"не удалось загрузить библиотеку {module}: {exc}. "
                                      "Установите зависимости: pip install -r requirements.txt")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((settings.host, settings.port))
        except OSError:
            _fail(EXIT_PORT_BUSY, f"порт {settings.port} на адресе {settings.host} занят. "
                                  "Укажите другой порт в переменной PORT.")

    uvicorn.run("app.main:create_app", factory=True, host=settings.host, port=settings.port,
                log_level=settings.log_level.lower(), **ssl_kwargs)


if __name__ == "__main__":
    main()
