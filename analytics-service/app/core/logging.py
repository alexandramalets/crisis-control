import logging
import re

_SECRET = re.compile(
    r"(?i)(x-service-key|service_key|bearer|password|passwd|secret|token)\s*[:=]?\s*\S+"
)
_JWT = re.compile(r"\beyJ[\w-]+\.[\w-]+\.[\w-]+")


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = _JWT.sub("***", _SECRET.sub(r"\1 ***", message))
        if redacted != message:
            record.msg, record.args = redacted, None
        return True


def configure_logging(level: str) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    filt = RedactFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(filt)
