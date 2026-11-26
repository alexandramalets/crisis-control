from app.integrations.analytics_client import AnalyticsServiceError
from app.integrations.analytics_contracts import AnalyzeResponse, ProcedureEnvelope


class FakeAnalyticsClient:
    """Имитация контракта /analytics/v1 без вызова микросервиса."""

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.payloads: list[dict] = []

    def get_health(self):
        self._raise()
        return {"status": "ok", "version": "0.1.0"}

    def get_capabilities(self):
        self._raise()
        return {"procedures": [{"type": "anomalies"}, {"type": "analyze"}]}

    def analyze(self, payload: dict) -> AnalyzeResponse:
        self._raise()
        self.payloads.append(payload)
        requested = payload.get("procedures") or [
            "validate", "anomalies", "correlation", "clustering", "forecast", "assessment",
        ]
        return AnalyzeResponse(
            service_version="0.1.0",
            request_id=payload.get("request_id"),
            random_state=payload.get("random_state"),
            procedures={name: self._envelope(name, payload) for name in requested},
        )

    def run_procedure(self, procedure: str, payload: dict) -> ProcedureEnvelope:
        self._raise()
        self.payloads.append(payload)
        return self._envelope(procedure, payload)

    def _raise(self):
        if self.error:
            raise self.error

    def _envelope(self, name: str, payload: dict) -> ProcedureEnvelope:
        periods = payload.get("periods") or ["2024-01"]
        codes = [item["code"] for item in payload.get("indicators") or []]
        primary = codes[0] if codes else "revenue"
        if name == "validate":
            return ProcedureEnvelope(status="ok", message="Проверка данных выполнена",
                                     result={"sufficient": True, "n_periods": len(periods)})
        if name == "anomalies":
            return ProcedureEnvelope(
                status="ok", message="Обнаружено аномалий: 1",
                result={
                    "method": "robust_z",
                    "baselines": [
                        {"indicator": code, "center": 10, "lower_bound": 1, "upper_bound": 19, "scale": 3}
                        for code in codes
                    ],
                    "anomalies": [{
                        "indicator": primary, "period": periods[-1], "value": 100,
                        "baseline": 10, "deviation": 90, "score": 5.5, "direction": "above",
                        "method": "robust_z",
                    }],
                },
            )
        if name == "correlation":
            pairs = []
            for i, a in enumerate(codes):
                for b in codes[i + 1:]:
                    pairs.append({
                        "indicator_a": a, "indicator_b": b, "coefficient": 1.0,
                        "p_value": 0.0, "n_observations": len(periods), "note": None,
                    })
            return ProcedureEnvelope(status="ok", message="Рассчитано пар", result={"method": "pearson", "pairs": pairs})
        if name == "clustering":
            members = [{"period": period, "cluster": index % 2, "pc1": float(index), "pc2": 0.0}
                       for index, period in enumerate(periods)]
            clusters = []
            for number in (0, 1):
                clusters.append({
                    "cluster": number, "size": sum(1 for m in members if m["cluster"] == number),
                    "centroid": {code: 10.0 + number for code in codes},
                })
            return ProcedureEnvelope(
                status="ok", message="Выделено кластеров: 2",
                result={"algorithm": "kmeans", "k": 2, "silhouette": 0.9, "inertia": 0.2,
                        "clusters": clusters, "members": members},
            )
        if name == "forecast":
            last = periods[-1]
            year, month = last.split("-")[:2]
            future = []
            month_n = int(month)
            year_n = int(year)
            horizon = (payload.get("forecast") or {}).get("horizon", payload.get("horizon", 3))
            for step in range(1, horizon + 1):
                month_n += 1
                if month_n == 13:
                    month_n, year_n = 1, year_n + 1
                value = 11.0 + step
                future.append({"period": f"{year_n}-{month_n:02d}", "value": value,
                               "lower": value - 1.0, "upper": value + 1.0})
            return ProcedureEnvelope(
                status="ok", message="Построен прогноз",
                result={"horizon": horizon, "series": [
                    {"indicator": code, "method": "simple_exponential_smoothing", "forecast": future}
                    for code in codes
                ]},
            )
        if name == "trends":
            return ProcedureEnvelope(
                status="ok", message="Рассчитаны тенденции",
                result={"items": [
                    {
                        "indicator": code, "slope": 0.12, "intercept": 10.0,
                        "kendall_tau": 0.5, "p_value": 0.2, "abs_change": 1.0,
                        "pct_change": 5.0, "consecutive_worsening": 0,
                        "label": "рост", "significant": False, "last_value": 11.0,
                        "last_period": periods[-1], "favorable": True,
                    }
                    for code in codes
                ]},
            )
        if name == "ratios":
            return ProcedureEnvelope(
                status="ok", message="Коэффициенты рассчитаны по доступным исходным данным",
                result={"items": [], "skipped": [
                    {"code": "current_ratio", "reason": "в наборе нет всех исходных показателей"},
                ]},
            )
        if name == "assessment":
            components = [
                {"indicator": code, "normalized_score": 0.4 if index == 0 else 0.5, "explanation": f"{code}: q"}
                for index, code in enumerate(codes)
            ]
            return ProcedureEnvelope(
                status="ok", message="Сводная оценка 45.0 из 100",
                result={"status": "ok", "score": 45.0, "components": components},
            )
        return ProcedureEnvelope(status="skipped", message="Неизвестная процедура")


def unavailable_client():
    return FakeAnalyticsClient(error=AnalyticsServiceError("Аналитический сервис недоступен. Повторите попытку позже."))
