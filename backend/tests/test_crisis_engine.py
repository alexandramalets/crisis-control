from app.services.crisis_engine import build_alerts, build_findings, recommendations_for


def test_solvency_requires_both_series():
    values = {"cash": [10, 8], "payables": [4, 5]}
    findings = build_findings(values=values, directions={}, ratios=[], period="2024-12")
    codes = {item["code"] for item in findings}
    assert "solvency_pressure" in codes
    recs = recommendations_for(findings)
    assert recs and recs[0]["finding_code"] == "solvency_pressure"


def test_missing_inputs_do_not_invent_problem():
    findings = build_findings(values={"cash": [1, 2]}, directions={}, ratios=[], period="2024-12")
    assert all(item["code"] != "solvency_pressure" or item["confidence"] != "confirmed" for item in findings)


def test_alerts_persistent_worsening():
    alerts = build_alerts(
        trends=[{
            "indicator": "profit", "consecutive_worsening": 4, "favorable": False,
            "last_value": 1, "last_period": "2024-12", "impact_direction": "higher_better",
        }],
        plans={}, norms={}, thresholds={}, directions={"profit": "higher_better"}, period="2024-12",
    )
    assert any(item["rule_code"] == "persistent_worsening" for item in alerts)


def test_plan_deviation_uses_direction():
    alerts = build_alerts(
        trends=[{
            "indicator": "revenue", "consecutive_worsening": 0, "favorable": True,
            "last_value": 80, "last_period": "2024-12",
        }],
        plans={"revenue": 100}, norms={}, thresholds={},
        directions={"revenue": "higher_better"}, period="2024-12",
    )
    assert any(item["rule_code"] == "plan_deviation" for item in alerts)
