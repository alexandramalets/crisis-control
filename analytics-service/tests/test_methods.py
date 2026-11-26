import numpy as np
from scipy.stats import median_abs_deviation, pearsonr

from app.methods.anomalies import detect_anomalies
from app.methods.assessment import assess
from app.methods.clustering import cluster
from app.methods.correlation import correlate
from app.methods.forecasting import forecast
from app.methods.frame import quality_report
from app.methods.ratios import compute_ratios
from app.methods.trends import detect_trends
from tests.helpers import frame_from, payload

PERIODS8 = [f"2020-{m:02d}" for m in range(1, 9)]
PERIODS6 = [f"2020-{m:02d}" for m in range(1, 7)]
PERIODS4 = ["2020", "2021", "2022", "2023"]


def test_validate_reports_insufficient_when_too_short():
    frame = frame_from(periods=["2020", "2021"], series={"A": [1.0, 2.0]})
    report = quality_report(frame)
    assert report["sufficient"] is False
    assert report["message"] == "Недостаточно данных"


def test_anomalies_robust_z_flags_known_outlier():
    values = [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 100.0]
    frame = frame_from(periods=PERIODS8, series={"X": values})
    result = detect_anomalies(frame, method="robust_z", threshold=3.0)
    assert result.status == "ok"
    found = result.result["anomalies"]
    assert len(found) == 1
    item = found[0]
    assert item["indicator"] == "X"
    assert item["period"] == "2020-08"
    assert item["value"] == 100.0
    median = float(np.median(values))
    mad = float(median_abs_deviation(values, scale="normal"))
    expected_score = (100.0 - median) / mad
    assert item["baseline"] == round(median, 6)
    assert item["deviation"] == round(100.0 - median, 6)
    assert item["score"] == round(expected_score, 6)
    assert item["direction"] == "above"
    assert item["method"] == "robust_z"
    assert expected_score > 3


def test_anomalies_mad_zero_falls_back_to_zscore():
    values = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0, 40.0]
    frame = frame_from(periods=PERIODS8, series={"X": values})
    # Классическая z-оценка одного выброса среди семи равных точек ≈ 2.47 < 3,
    # поэтому порог 2, чтобы проверить сам переход MAD→zscore, а не силу критерия.
    result = detect_anomalies(frame, method="robust_z", threshold=2.0)
    assert result.status == "ok"
    assert any("MAD равен нулю" in w for w in result.warnings)
    assert result.result["baselines"][0]["method"] == "zscore"
    found = result.result["anomalies"]
    assert len(found) == 1
    assert found[0]["period"] == "2020-08"
    assert found[0]["value"] == 40.0
    assert found[0]["method"] == "zscore"
    assert found[0]["direction"] == "above"
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1))
    assert found[0]["baseline"] == round(mean, 6)
    assert found[0]["score"] == round((40.0 - mean) / std, 6)


def test_anomalies_constant_series_has_none():
    frame = frame_from(periods=PERIODS8, series={"X": [7.0] * 8})
    result = detect_anomalies(frame)
    assert result.status == "ok"
    assert result.result["anomalies"] == []
    assert result.result["baselines"][0]["scale"] == 0.0


def test_anomalies_insufficient_observations():
    frame = frame_from(periods=["2020", "2021", "2022"], series={"X": [1.0, 2.0, 9.0]})
    result = detect_anomalies(frame, min_observations=6)
    assert result.status == "skipped"
    assert result.result is None


def test_correlation_perfect_linear_pair():
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
    y = [2.0, 4.0, 6.0, 8.0, 10.0, 12.0]
    frame = frame_from(periods=PERIODS6, series={"A": x, "B": y})
    result = correlate(frame)
    assert result.status == "ok"
    pair = result.result["pairs"][0]
    expected, p_value = pearsonr(x, y)
    assert pair["coefficient"] == round(float(expected), 6)
    assert pair["coefficient"] == 1.0
    assert pair["n_observations"] == 6
    assert abs(pair["p_value"] - round(float(p_value), 6)) < 1e-12
    assert result.result["matrix"] == [[1.0, 1.0], [1.0, 1.0]]
    assert "причин" in result.result["interpretation"].lower()


def test_correlation_constant_column_is_null():
    frame = frame_from(periods=PERIODS6, series={"A": [1, 2, 3, 4, 5, 6], "B": [3, 3, 3, 3, 3, 3]})
    result = correlate(frame)
    assert result.status == "skipped" or result.result["pairs"][0]["coefficient"] is None
    if result.status == "ok":
        assert result.result["pairs"][0]["coefficient"] is None
        assert "постоянный" in result.result["pairs"][0]["note"]


def test_correlation_pairwise_missing_values():
    a = [1.0, 2.0, None, 4.0, 5.0, 6.0]
    b = [2.0, 4.0, 6.0, None, 10.0, 12.0]
    frame = frame_from(periods=PERIODS6, series={"A": a, "B": b})
    result = correlate(frame)
    assert result.status == "ok"
    assert result.result["pairs"][0]["n_observations"] == 4
    assert result.result["pairs"][0]["coefficient"] == 1.0


def test_correlation_too_few_periods():
    frame = frame_from(periods=["2020", "2021"], series={"A": [1.0, 2.0], "B": [2.0, 4.0]})
    result = correlate(frame, min_observations=4)
    assert result.status == "skipped"


def test_clustering_two_separated_groups():
    periods = [f"p{i}" for i in range(8)]
    x = [0.0, 0.1, 0.0, 0.1, 10.0, 10.1, 10.0, 10.1]
    y = [0.0, 0.0, 0.1, 0.1, 10.0, 10.0, 10.1, 10.1]
    frame = frame_from(periods=periods, series={"X": x, "Y": y})
    result = cluster(frame, k=2, random_state=42)
    assert result.status == "ok"
    assert result.result["algorithm"] == "kmeans"
    assert result.result["scaler"] == "standard"
    assert result.result["k"] == 2
    assert result.result["silhouette"] is not None
    assert result.result["silhouette"] > 0.8
    labels = [m["cluster"] for m in result.result["members"]]
    assert set(labels[:4]) == {labels[0]}
    assert set(labels[4:]) == {labels[4]}
    assert labels[0] != labels[4]
    assert "кризис" in result.result["interpretation"].lower()
    repeat = cluster(frame, k=2, random_state=42)
    assert [m["cluster"] for m in repeat.result["members"]] == labels


def test_clustering_insufficient_rows():
    frame = frame_from(periods=["a", "b"], series={"X": [1.0, 2.0], "Y": [3.0, 4.0]})
    result = cluster(frame, k=2)
    assert result.status == "skipped"


def test_clustering_auto_k_returns_silhouette_by_k():
    periods = [f"p{i}" for i in range(8)]
    x = [0.0, 0.1, 0.0, 0.1, 10.0, 10.1, 10.0, 10.1]
    y = [0.0, 0.0, 0.1, 0.1, 10.0, 10.0, 10.1, 10.1]
    result = cluster(frame_from(periods=periods, series={"X": x, "Y": y}), k="auto")
    assert result.status == "ok"
    assert result.result["k_selection"] == "silhouette"
    assert "2" in result.result["silhouette_by_k"]


def test_forecast_constant_series_equals_level():
    values = [5.0, 5.0, 5.0, 5.0, 5.0, 5.0]
    frame = frame_from(periods=PERIODS6, series={"X": values})
    result = forecast(frame, horizon=3)
    assert result.status == "ok"
    series = result.result["series"][0]
    assert series["method"] == "simple_exponential_smoothing"
    assert [p["period"] for p in series["forecast"]] == ["2020-07", "2020-08", "2020-09"]
    for point in series["forecast"]:
        assert abs(point["value"] - 5.0) < 1e-6
    assert [h["value"] for h in series["history"]] == values


def test_forecast_insufficient_does_not_invent_values():
    frame = frame_from(periods=["2020", "2021", "2022"], series={"X": [1.0, 2.0, 3.0]})
    result = forecast(frame, horizon=3)
    assert result.status == "skipped"
    assert result.result is None
    assert "не создаются" in result.message.lower() or "недостаточно" in result.message.lower()


def test_forecast_annual_horizon_dates():
    frame = frame_from(periods=PERIODS4, series={"X": [10.0, 11.0, 12.0, 13.0]})
    result = forecast(frame, horizon=2)
    assert result.status == "ok"
    dates = [p["period"] for p in result.result["series"][0]["forecast"]]
    assert dates[0].startswith("2024")
    assert dates[1].startswith("2025")


def test_assessment_known_weighted_score():
    frame = frame_from(
        periods=PERIODS4,
        series={"Profit": [10.0, 20.0, 30.0, 40.0], "Debt": [80.0, 70.0, 60.0, 50.0]},
        directions={"Profit": "higher_better", "Debt": "lower_better"},
        weights={"Profit": 1.0, "Debt": 1.0},
        bounds={"Profit": (0.0, 100.0), "Debt": (0.0, 100.0)},
    )
    result = assess(frame)
    assert result.status == "ok"
    assert result.result["status"] == "ok"
    # q_profit = 40/100 = 0.4; q_debt = (100-50)/100 = 0.5; C = 100*(0.5*0.4 + 0.5*0.5) = 45
    assert result.result["score"] == 45.0
    by_code = {c["indicator"]: c for c in result.result["components"]}
    assert by_code["Profit"]["normalized_score"] == 0.4
    assert by_code["Debt"]["normalized_score"] == 0.5
    assert by_code["Profit"]["impact_direction"] == "higher_better"


def test_assessment_insufficient_data_status():
    frame = frame_from(periods=["2020", "2021"], series={"A": [1.0, 2.0]})
    result = assess(frame)
    assert result.status == "skipped"
    assert result.message == "Недостаточно данных"


def test_assessment_all_constant_without_bounds():
    frame = frame_from(periods=PERIODS4, series={"A": [3.0, 3.0, 3.0, 3.0]})
    result = assess(frame)
    assert result.status == "skipped"
    assert result.result["status"] == "insufficient_data"
    assert result.result["status_label"] == "Недостаточно данных"
    assert result.result["score"] is None


def test_current_ratio_skips_zero_denominator():
    frame = frame_from(
        periods=PERIODS4,
        series={
            "current_assets": [100.0, 110.0, 120.0, 130.0],
            "current_liabilities": [50.0, 0.0, 40.0, 40.0],
        },
    )
    result = compute_ratios(frame)
    assert result.status == "ok"
    item = next(row for row in result.result["items"] if row["code"] == "current_ratio")
    zeros = [row for row in item["series"] if row["reason"]]
    assert zeros
    assert item["last_value"] == 130.0 / 40.0


def test_ratio_missing_inputs_is_skipped_not_zero_filled():
    frame = frame_from(periods=PERIODS4, series={"revenue": [1.0, 2.0, 3.0, 4.0]})
    result = compute_ratios(frame)
    skipped = {row["code"] for row in result.result["skipped"]}
    assert "current_ratio" in skipped
    assert all(row["code"] != "current_ratio" for row in result.result["items"])


def test_trends_respect_direction():
    frame = frame_from(
        periods=PERIODS8,
        series={"Debt": list(range(8))},
        directions={"Debt": "lower_better"},
    )
    result = detect_trends(frame)
    assert result.status == "ok"
    item = result.result["items"][0]
    assert item["indicator"] == "Debt"
    assert item["consecutive_worsening"] >= 1 or item.get("favorable") is False
