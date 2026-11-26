import httpx

from app.core.config import get_settings
from app.integrations.analytics_client import AnalyticsClient, AnalyticsServiceError
from app.integrations.circuit_breaker import CircuitBreaker


def _client(handler, **settings_overrides) -> AnalyticsClient:
    settings = get_settings()
    for name, value in settings_overrides.items():
        object.__setattr__(settings, name, value) if False else setattr(settings, name, value)
    return AnalyticsClient(
        settings,
        breaker=CircuitBreaker(settings.analytics_breaker_failures, settings.analytics_breaker_reset_seconds),
        transport=httpx.MockTransport(handler),
    )


def test_https_client_receives_timeout_and_private_ca(monkeypatch, tmp_path):
    ca_file = tmp_path / "ca.crt"
    ca_file.write_text("not-a-certificate")
    seen = {}
    real_client = httpx.Client

    def wrapped(*args, **kwargs):
        seen["verify"] = kwargs.get("verify")
        seen["timeout"] = kwargs.get("timeout")
        return real_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", wrapped)
    settings = get_settings().model_copy(update={"analytics_tls_ca_file": ca_file})
    client = AnalyticsClient(settings, breaker=CircuitBreaker(3, 30), transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"status": "ok"})
    ))
    try:
        client.get_health()
    except Exception:
        pass
    assert seen["verify"] == str(ca_file)
    assert seen["timeout"] == settings.analytics_timeout_seconds


def test_health_ok():
    def handler(request: httpx.Request):
        assert request.headers["X-Service-Key"] == "k" * 32
        return httpx.Response(200, json={"status": "ok", "version": "0.1.0", "libraries": {}})

    assert _client(handler).get_health()["version"] == "0.1.0"


def test_timeout_is_unavailable():
    def handler(request: httpx.Request):
        raise httpx.ReadTimeout("slow")

    try:
        _client(handler).get_health()
    except AnalyticsServiceError as exc:
        assert exc.unavailable
        assert "недоступен" in exc.message.lower()
    else:
        raise AssertionError("ожидалась AnalyticsServiceError")


def test_circuit_breaker_opens_after_failures():
    calls = {"n": 0}

    def handler(request: httpx.Request):
        calls["n"] += 1
        raise httpx.ConnectError("down")

    client = _client(handler)
    client.settings.analytics_retries = 0
    client.breaker = CircuitBreaker(2, 60)
    for _ in range(2):
        try:
            client.get_health()
        except AnalyticsServiceError:
            pass
    try:
        client.get_health()
    except AnalyticsServiceError as exc:
        assert "недоступен" in exc.message.lower()
    else:
        raise AssertionError("ожидалась AnalyticsServiceError")
    assert calls["n"] == 2


def test_payload_size_limit():
    settings = get_settings().model_copy(update={"analytics_max_payload_bytes": 32})
    client = AnalyticsClient(settings, breaker=CircuitBreaker(3, 30), transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json={"status": "ok"})
    ))
    try:
        client.analyze({"periods": ["2020-01"] * 50, "indicators": []})
    except AnalyticsServiceError as exc:
        assert not exc.unavailable
        assert "большой" in exc.message.lower()
    else:
        raise AssertionError("ожидалась AnalyticsServiceError")


def test_invalid_json_is_contract_error():
    def handler(request: httpx.Request):
        return httpx.Response(200, text="not-json")

    try:
        _client(handler).get_health()
    except AnalyticsServiceError as exc:
        assert "некорректн" in exc.message.lower()
    else:
        raise AssertionError("ожидалась AnalyticsServiceError")
