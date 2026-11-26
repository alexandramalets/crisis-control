"""Предохранитель: после серии сбоев запросы к сервису не отправляются до паузы."""

import threading
import time
from enum import StrEnum


class BreakerState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__("Аналитический сервис временно недоступен")


class CircuitBreaker:
    def __init__(self, failure_threshold: int, reset_seconds: float):
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._failures = 0
        self._opened_at = 0.0
        self._state = BreakerState.CLOSED
        self._lock = threading.Lock()

    @property
    def state(self) -> BreakerState:
        return self._state

    def before_call(self) -> None:
        with self._lock:
            if self._state == BreakerState.OPEN:
                elapsed = time.monotonic() - self._opened_at
                if elapsed >= self.reset_seconds:
                    self._state = BreakerState.HALF_OPEN
                    return
                raise CircuitOpenError(self.reset_seconds - elapsed)

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = BreakerState.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state == BreakerState.HALF_OPEN or self._failures >= self.failure_threshold:
                self._state = BreakerState.OPEN
                self._opened_at = time.monotonic()
