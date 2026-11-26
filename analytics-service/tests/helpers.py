from app.methods.frame import build_frame
from app.schemas.common import DataPayload, IndicatorSeries, ImpactDirection


def payload(periods: list[str], series: dict[str, list[float | None]], *,
            directions: dict[str, ImpactDirection] | None = None,
            weights: dict[str, float] | None = None,
            bounds: dict[str, tuple[float, float]] | None = None,
            random_state: int = 42, request_id: str | None = "test") -> DataPayload:
    indicators = []
    for code, values in series.items():
        low = high = None
        if bounds and code in bounds:
            low, high = bounds[code]
        indicators.append(IndicatorSeries(
            code=code,
            values=values,
            impact_direction=(directions or {}).get(code, "neutral"),
            weight=(weights or {}).get(code),
            lower_bound=low,
            upper_bound=high,
        ))
    return DataPayload(request_id=request_id, random_state=random_state, periods=periods, indicators=indicators)


def frame_from(**kwargs):
    return build_frame(payload(**kwargs))
