"""Проверка демо-набора: импорт-разбор приложения + конвейер аналитики."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / "backend"))
sys.path.insert(0, str(ROOT.parent / "analytics-service"))

from generate_promtech import COLUMNS, RU_HEADERS, build_series, last_findings, parse_with_app  # noqa: E402


DIRECTIONS = {
    "revenue": "higher_better", "sales_volume": "higher_better", "output": "higher_better",
    "cogs": "lower_better", "profit": "higher_better", "net_profit": "higher_better",
    "receivables": "lower_better", "overdue_receivables": "lower_better",
    "payables": "lower_better", "inventory": "neutral", "cash": "higher_better",
    "current_assets": "higher_better", "current_liabilities": "lower_better",
    "equity": "higher_better", "total_assets": "higher_better", "long_term_debt": "lower_better",
    "cf_operating": "higher_better", "cf_investing": "neutral", "cf_financing": "neutral",
    "personnel": "neutral",
}


def load_compose_key() -> str | None:
    env_path = ROOT.parent / ".env"
    if not env_path.is_file():
        return None
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("ANALYTICS_SERVICE_KEY="):
            return line.split("=", 1)[1].strip()
    return None


def payload(rows: list[dict]) -> dict:
    periods = [row["period"] for row in rows]
    indicators = []
    for code in COLUMNS:
        if code == "period":
            continue
        indicators.append({
            "code": code,
            "values": [float(row[code]) for row in rows],
            "impact_direction": DIRECTIONS[code],
            "weight": 1.0,
        })
    return {
        "random_state": 42,
        "periods": periods,
        "indicators": indicators,
        "procedures": [
            "validate", "ratios", "anomalies", "trends", "correlation",
            "clustering", "forecast", "assessment",
        ],
        "anomalies": {"method": "robust_z", "threshold": 3, "min_observations": 6},
        "correlation": {"method": "pearson", "min_observations": 4},
        "clustering": {"k": "auto", "k_min": 2, "k_max": 6},
        "forecast": {"horizon": 3, "model": "auto"},
    }


def call_analytics(body: dict, key: str) -> dict:
    request = urllib.request.Request(
        "http://127.0.0.1:8001/analytics/v1/analyze",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-Service-Key": key},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))


def summarize(name: str, procedures: dict) -> None:
    print(f"\n=== {name} ===")
    for code, item in procedures.items():
        status = item.get("status")
        message = item.get("message")
        extra = ""
        result = item.get("result") or {}
        if code == "ratios":
            extra = f" коэффициентов={len(result.get('items') or [])} пропущено={len(result.get('skipped') or [])}"
            skipped = result.get("skipped") or []
            if skipped:
                extra += " (" + ", ".join(s["code"] for s in skipped) + ")"
        if code == "anomalies":
            extra = f" точек={len(result.get('anomalies') or [])}"
        if code == "trends":
            extra = f" рядов={len(result.get('items') or result.get('trends') or [])}"
        if code == "correlation":
            extra = f" пар={len(result.get('pairs') or [])}"
        if code == "clustering":
            extra = f" k={result.get('k')} групп={len(result.get('clusters') or [])}"
        if code == "forecast":
            series = result.get("series") or []
            extra = f" рядов={len(series)}"
        if code == "assessment":
            extra = f" балл={result.get('score')}"
        print(f"  {code}: {status} — {message}{extra}")


def main() -> int:
    for filename in (
        "promtech_service_initial.xlsx",
        "promtech_service_initial.csv",
        "promtech_service_recovery.xlsx",
        "promtech_service_recovery.csv",
    ):
        report = parse_with_app(ROOT / filename)
        print(filename, "ready", report["ready"], "cols", len(report["mapped"]), "errors", len(report["errors"]))
        if not report["ready"]:
            return 1
    quality = parse_with_app(ROOT / "promtech_service_quality_test.xlsx")
    print("quality_test ready", quality["ready"], "errors", len(quality["errors"]))
    if quality["ready"]:
        return 1

    initial = build_series("initial")
    recovery = build_series("recovery")
    print("findings initial", last_findings(initial))
    print("findings recovery", last_findings(recovery))

    key = load_compose_key()
    if not key:
        print("Нет ANALYTICS_SERVICE_KEY — конвейер аналитики пропущен")
        return 0
    try:
        for label, rows in (("initial", initial), ("recovery", recovery)):
            data = call_analytics(payload(rows), key)
            summarize(label, data.get("procedures") or {})
    except OSError as exc:
        print("Аналитический микросервис сейчас не запущен:", exc)
        print("Разбор загрузки и правила проблем проверены без него.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
