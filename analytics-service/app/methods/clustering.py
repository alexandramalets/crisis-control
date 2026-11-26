"""Кластеризация k-средних с масштабированием. Номера кластеров — не уровни риска."""

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from app.methods.frame import AnalysisFrame
from app.methods.result import procedure, skipped
from app.schemas.common import ProcedureResult

NOTE = "Номер группы не означает кризис. Сравнивайте центры."


def cluster(frame: AnalysisFrame, *, k: int | str = "auto", k_min: int = 2, k_max: int = 6,
            random_state: int | None = None) -> ProcedureResult:
    random_state = frame.random_state if random_state is None else random_state
    complete = ~np.isnan(frame.values).any(axis=1)
    n = int(complete.sum())
    if n < k_min * 2:
        return skipped(
            f"Недостаточно полных наблюдений для кластеризации (есть {n}, нужно не менее {k_min * 2})"
        )
    if frame.n_indicators < 1:
        return skipped("Нет показателей для кластеризации")

    matrix = frame.values[complete]
    periods = [period for period, keep in zip(frame.periods, complete, strict=True) if keep]
    scaler = StandardScaler()
    scaled = scaler.fit_transform(matrix)

    k_max_eff = min(k_max, n - 1)
    if k_max_eff < k_min:
        return skipped("Слишком мало наблюдений, чтобы выбрать число кластеров")

    if k == "auto" or k is None:
        chosen, silhouette_by_k = _choose_k(scaled, k_min, k_max_eff, random_state)
    else:
        chosen = int(k)
        silhouette_by_k = {}
        if chosen < 1 or chosen > n:
            return skipped(f"Число кластеров k={chosen} недопустимо при {n} наблюдениях")
        if chosen == 1:
            return _single_cluster(periods, matrix, scaled, scaler, frame.codes, random_state)

    model = KMeans(n_clusters=chosen, n_init=10, random_state=random_state)
    labels = model.fit_predict(scaled)
    silhouette = None
    if chosen >= 2 and n > chosen:
        silhouette = float(silhouette_score(scaled, labels))

    coords = _pca(scaled)
    members = [
        {
            "period": period,
            "cluster": int(label),
            "pc1": _r(coords[i, 0]),
            "pc2": _r(coords[i, 1]) if coords.shape[1] > 1 else 0.0,
        }
        for i, (period, label) in enumerate(zip(periods, labels, strict=True))
    ]
    clusters = []
    original_centers = scaler.inverse_transform(model.cluster_centers_)
    overall = {code: _r(float(np.nanmean(matrix[:, j]))) for j, code in enumerate(frame.codes)}
    for number in range(chosen):
        mask = labels == number
        centroid = {code: _r(original_centers[number, j]) for j, code in enumerate(frame.codes)}
        vs_overall = {code: _r(centroid[code] - overall[code]) for code in frame.codes}
        clusters.append({
            "cluster": number,
            "size": int(mask.sum()),
            "centroid": centroid,
            "centroid_scaled": {code: _r(model.cluster_centers_[number, j]) for j, code in enumerate(frame.codes)},
            "vs_overall": vs_overall,
            "periods": [period for period, keep in zip(periods, mask, strict=True) if keep],
            "note": "Отличие от среднего профиля набора, без ярлыка «кризис».",
        })

    dropped = frame.n_periods - n
    warnings = []
    if dropped:
        warnings.append(f"Исключено периодов с пропусками: {dropped}")
    return procedure(
        "ok",
        f"Выделено кластеров: {chosen}" + (f", силуэт {silhouette:.3f}" if silhouette is not None else ""),
        {
            "algorithm": "kmeans",
            "scaler": "standard",
            "k": chosen,
            "k_selection": "silhouette" if k == "auto" else "user",
            "overall_profile": overall,
            "k_min": k_min,
            "k_max": k_max_eff,
            "random_state": random_state,
            "n_init": 10,
            "n_observations": n,
            "n_features": frame.n_indicators,
            "silhouette": None if silhouette is None else _r(silhouette),
            "inertia": _r(float(model.inertia_)),
            "silhouette_by_k": silhouette_by_k,
            "clusters": clusters,
            "members": members,
            "interpretation": NOTE,
        },
        warnings,
    )


def _choose_k(scaled, k_min, k_max, random_state) -> tuple[int, dict]:
    scores = {}
    best_k, best_score = k_min, -1.0
    for candidate in range(k_min, k_max + 1):
        labels = KMeans(n_clusters=candidate, n_init=10, random_state=random_state).fit_predict(scaled)
        if len(set(labels)) < 2:
            continue
        score = float(silhouette_score(scaled, labels))
        scores[str(candidate)] = round(score, 6)
        if score > best_score:
            best_k, best_score = candidate, score
    return best_k, scores


def _single_cluster(periods, matrix, scaled, scaler, codes, random_state):
    center = matrix.mean(axis=0)
    members = [{"period": p, "cluster": 0, "pc1": 0.0, "pc2": 0.0} for p in periods]
    return procedure(
        "ok", "Задан один кластер; коэффициент силуэта не применяется",
        {
            "algorithm": "kmeans", "k": 1, "k_selection": "user", "random_state": random_state,
            "silhouette": None, "inertia": 0.0, "n_observations": len(periods),
            "clusters": [{"cluster": 0, "size": len(periods),
                          "centroid": {c: _r(center[i]) for i, c in enumerate(codes)}}],
            "members": members, "interpretation": NOTE,
        },
        ["При k=1 коэффициент силуэта не определён"],
    )


def _pca(scaled: np.ndarray) -> np.ndarray:
    components = min(2, scaled.shape[0], scaled.shape[1])
    if components < 1:
        return np.zeros((scaled.shape[0], 2))
    coords = PCA(n_components=components, random_state=0).fit_transform(scaled)
    if coords.shape[1] == 1:
        coords = np.column_stack([coords, np.zeros(len(coords))])
    return coords


def _r(value: float) -> float:
    return round(float(value), 6)
