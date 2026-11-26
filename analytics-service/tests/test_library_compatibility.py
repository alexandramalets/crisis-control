"""Проверка совместимости закреплённых версий библиотек между собой (без реализации алгоритмов)."""

import warnings

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.cluster import KMeans
from statsmodels.tsa.holtwinters import SimpleExpSmoothing


def test_scientific_stack_works_together():
    index = pd.period_range("2024-01", periods=24, freq="M").to_timestamp()
    series = pd.Series(np.linspace(100.0, 150.0, 24), index=index)

    assert stats.median_abs_deviation(series, scale="normal") > 0

    labels = KMeans(n_clusters=2, n_init=10, random_state=42).fit_predict(series.to_frame())
    assert set(labels) == {0, 1}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        forecast = SimpleExpSmoothing(series, initialization_method="estimated").fit().forecast(3)
    assert len(forecast) == 3
