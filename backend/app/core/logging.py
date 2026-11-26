import logging
import re

_SECRET_PATTERNS = [
    (re.compile(r"(?i)(bearer\s+)[\w\-.~+/]+=*"), r"\1***"),
    (re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+"), "***"),
    (re.compile(r"(?i)((?:password|passwd|secret|token|refresh_token|access_token|service_key|x-service-key)[\"']?\s*[:=]\s*[\"']?)[^\s\"',;&]+"),
     r"\1***"),
]


def redact(text: str) -> str:
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class RedactSecretsFilter(logging.Filter):
    """Последний рубеж: маскирует токены и пароли, если они попали в сообщение журнала."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = redact(message)
        if redacted != message:
            record.msg, record.args = redacted, None
        return True


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    secrets_filter = RedactSecretsFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(secrets_filter)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).addFilter(secrets_filter)
