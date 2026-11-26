class ServiceError(Exception):
    """Ошибка бизнес-логики с понятным пользователю сообщением."""

    status_code = 400
    code = "service_error"

    def __init__(self, message: str, details=None, code: str | None = None, headers: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details
        self.headers = headers
        if code is not None:
            self.code = code


class AuthenticationError(ServiceError):
    status_code = 401
    code = "not_authenticated"

    def __init__(self, message: str = "Требуется авторизация", code: str | None = None):
        super().__init__(message, code=code, headers={"WWW-Authenticate": "Bearer"})


class PermissionDeniedError(ServiceError):
    status_code = 403
    code = "forbidden"


class NotFoundError(ServiceError):
    status_code = 404
    code = "not_found"


class ConflictError(ServiceError):
    status_code = 409
    code = "conflict"


class PayloadTooLargeError(ServiceError):
    status_code = 413
    code = "payload_too_large"


class ValidationFailedError(ServiceError):
    status_code = 422
    code = "validation_error"


class TooManyAttemptsError(ServiceError):
    status_code = 429
    code = "account_locked"


class AnalyticsUnavailableError(ServiceError):
    status_code = 503
    code = "analytics_unavailable"


class AnalyticsContractError(ServiceError):
    status_code = 502
    code = "analytics_invalid_response"
