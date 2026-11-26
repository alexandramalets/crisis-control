"""Anti-Corruption Layer: единственное место HTTP-вызовов аналитического микросервиса."""

import json
import logging
from functools import lru_cache

import httpx

from app.core.config import Settings, get_settings
from app.integrations.analytics_contracts import AnalyzeResponse, ProcedureEnvelope
from app.integrations.circuit_breaker import CircuitBreaker, CircuitOpenError

logger = logging.getLogger(__name__)

UNAVAILABLE = "Аналитический сервис недоступен. Повторите попытку позже."
INVALID = "Аналитический сервис вернул некорректный ответ."
PAYLOAD_TOO_LARGE = "Слишком большой объём данных для передачи в аналитический сервис."


class AnalyticsServiceError(Exception):
    """Сбой вызова ML-сервиса. Не содержит значений показателей."""

    def __init__(self, message: str, *, unavailable: bool = True):
        super().__init__(message)
        self.message = message
        self.unavailable = unavailable


class AnalyticsClient:
    def __init__(self, settings: Settings, breaker: CircuitBreaker | None = None,
                 transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport
        self.breaker = breaker or CircuitBreaker(
            settings.analytics_breaker_failures, settings.analytics_breaker_reset_seconds,
        )

    def get_health(self) -> dict:
        return self._request("GET", "/analytics/v1/health")

    def get_capabilities(self) -> dict:
        return self._request("GET", "/analytics/v1/capabilities")

    def analyze(self, payload: dict) -> AnalyzeResponse:
        body = self._request("POST", "/analytics/v1/analyze", payload)
        try:
            return AnalyzeResponse.model_validate(body)
        except Exception as exc:
            logger.error("Некорректная структура ответа analyze: %s", type(exc).__name__)
            raise AnalyticsServiceError(INVALID, unavailable=False) from exc

    def run_procedure(self, procedure: str, payload: dict) -> ProcedureEnvelope:
        path = {
            "validate": "/analytics/v1/validate",
            "anomalies": "/analytics/v1/anomalies",
            "correlation": "/analytics/v1/correlation",
            "clustering": "/analytics/v1/clustering",
            "forecast": "/analytics/v1/forecast",
            "assessment": "/analytics/v1/assessment",
            "trends": "/analytics/v1/trends",
            "ratios": "/analytics/v1/ratios",
        }.get(procedure)
        if path is None:
            raise AnalyticsServiceError(f"Неизвестная процедура: {procedure}", unavailable=False)
        body = self._request("POST", path, payload)
        try:
            return ProcedureEnvelope.model_validate(body)
        except Exception as exc:
            logger.error("Некорректная структура ответа %s: %s", procedure, type(exc).__name__)
            raise AnalyticsServiceError(INVALID, unavailable=False) from exc

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        if payload is not None:
            encoded = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
            if len(encoded) > self.settings.analytics_max_payload_bytes:
                raise AnalyticsServiceError(PAYLOAD_TOO_LARGE, unavailable=False)
        try:
            self.breaker.before_call()
        except CircuitOpenError:
            logger.warning("Предохранитель открыт, запрос %s %s не отправлен", method, path)
            raise AnalyticsServiceError(UNAVAILABLE) from None

        retries = max(self.settings.analytics_retries, 1)
        last_error: Exception | None = None
        urls = _candidate_urls(self.settings.analytics_service_url)
        for attempt in range(retries + 1):
            base = urls[min(attempt, len(urls) - 1)]
            try:
                response = self._send(method, path, payload, base_url=base)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout) as exc:
                last_error = exc
                logger.warning("Сеть %s %s (%s) попытка %s: %s", method, path, base, attempt + 1, type(exc).__name__)
                continue
            except httpx.HTTPError as exc:
                self.breaker.record_failure()
                logger.warning("HTTP-сбой %s %s: %s", method, path, type(exc).__name__)
                raise AnalyticsServiceError(UNAVAILABLE) from exc
            return self._read(response)
        self.breaker.record_failure()
        raise AnalyticsServiceError(UNAVAILABLE) from last_error

    def _tls_verify(self) -> bool | str:
        ca_file = self.settings.analytics_tls_ca_file
        return str(ca_file) if ca_file is not None else True

    def _send(self, method: str, path: str, payload: dict | None, *, base_url: str | None = None) -> httpx.Response:
        headers = {"X-Service-Key": self.settings.analytics_service_key.get_secret_value()}
        with httpx.Client(
            base_url=(base_url or self.settings.analytics_service_url).rstrip("/"),
            timeout=self.settings.analytics_timeout_seconds,
            headers=headers,
            transport=self.transport,
            verify=self._tls_verify(),
        ) as client:
            return client.request(method, path, json=payload)

    def _read(self, response: httpx.Response) -> dict:
        if response.status_code == 401:
            self.breaker.record_failure()
            raise AnalyticsServiceError("Аналитический сервис отклонил межсервисный ключ")
        if response.status_code >= 500:
            self.breaker.record_failure()
            logger.error("Аналитический сервис ответил %s на %s", response.status_code, response.request.url.path)
            raise AnalyticsServiceError(UNAVAILABLE)
        if response.status_code >= 400:
            logger.warning("Аналитический сервис ответил %s", response.status_code)
            message = _error_message(response) or UNAVAILABLE
            raise AnalyticsServiceError(message, unavailable=response.status_code >= 500)
        try:
            body = response.json()
        except ValueError as exc:
            self.breaker.record_failure()
            raise AnalyticsServiceError(INVALID, unavailable=False) from exc
        if not isinstance(body, dict):
            raise AnalyticsServiceError(INVALID, unavailable=False)
        self.breaker.record_success()
        return body


def _candidate_urls(primary: str) -> list[str]:
    urls = [primary.rstrip("/")]
    for item in ("http://analytics-service:8001", "http://127.0.0.1:8001", "http://localhost:8001",
                 "http://host.docker.internal:8001"):
        if item not in urls:
            urls.append(item)
    return urls


def _error_message(response: httpx.Response) -> str | None:
    try:
        body = response.json()
    except ValueError:
        return None
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    return None


@lru_cache
def _shared_breaker(failures: int, reset: float) -> CircuitBreaker:
    return CircuitBreaker(failures, reset)


def get_analytics_client(settings: Settings | None = None) -> AnalyticsClient:
    settings = settings or get_settings()
    breaker = _shared_breaker(settings.analytics_breaker_failures, settings.analytics_breaker_reset_seconds)
    return AnalyticsClient(settings, breaker)


def get_health(settings: Settings) -> dict:
    return get_analytics_client(settings).get_health()


def get_capabilities(settings: Settings) -> dict:
    return get_analytics_client(settings).get_capabilities()
