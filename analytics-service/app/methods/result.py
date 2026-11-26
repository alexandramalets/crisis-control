from typing import Any

import numpy as np

from app.schemas.common import ProcedureResult, ProcedureStatus


def jsonable(value: Any) -> Any:
    """Скаляры numpy нельзя отдать в JSON-ответ FastAPI."""
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, np.generic):
        return value.item()
    return value


def procedure(status: ProcedureStatus, message: str | None = None, result: dict[str, Any] | None = None,
              warnings: list[str] | None = None) -> ProcedureResult:
    return ProcedureResult(
        status=status,
        message=message,
        result=None if result is None else jsonable(result),
        warnings=warnings or [],
    )


def skipped(message: str, warnings: list[str] | None = None) -> ProcedureResult:
    return procedure("skipped", message, None, warnings)


def failed(message: str) -> ProcedureResult:
    return procedure("error", message, None)
