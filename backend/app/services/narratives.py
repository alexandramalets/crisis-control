"""Текстовые уровни интерпретации по сохранённым результатам процедур."""

from app.models.enums import ProcedureStatus
from app.schemas.analysis import LayeredNarrative
from app.services.assessment_labels import ASSESSMENT_DISCLAIMER, ASSESSMENT_METHOD, interpret_score


def _status(procedure) -> str:
    return procedure.status.value if procedure and procedure.status else "missing"


def assessment_narrative(assessment, *, organization_name: str | None = None) -> LayeredNarrative:
    org = f"организации «{organization_name}»" if organization_name else "выбранной организации"
    if assessment is None:
        return LayeredNarrative(
            brief=f"Сводная оценка {org} не входила в запуск или не сохранилась.",
            details=["Результат не переносится с других организаций."],
            technical=[ASSESSMENT_METHOD],
        )
    if assessment.score is None:
        return LayeredNarrative(
            brief=assessment.message or f"Сводная оценка {org} не рассчитана: недостаточно данных.",
            details=[
                "Нужно не менее трёх периодов и хотя бы один показатель с вариацией.",
                ASSESSMENT_DISCLAIMER,
            ],
            technical=[ASSESSMENT_METHOD, assessment.message or ""],
        )
    zone = assessment.interpretation or interpret_score(assessment.score) or "Рассчитано"
    weak = sorted(assessment.components or [], key=lambda item: float(item.normalized_score))[:3]
    strong = sorted(assessment.components or [], key=lambda item: float(item.normalized_score), reverse=True)[:3]
    details = [
        f"Балл {float(assessment.score):.0f} из 100 для {org} — зона «{zone}».",
        "Шкала — ориентир по рядам этого набора.",
    ]
    if weak:
        details.append("Ниже относительно собственного диапазона: " + ", ".join(c.indicator_name for c in weak) + ".")
    if strong:
        details.append("Ближе к благоприятной стороне диапазона: " + ", ".join(c.indicator_name for c in strong) + ".")
    technical = [ASSESSMENT_METHOD]
    for item in assessment.components or []:
        contrib = f", вклад {item.contribution}" if item.contribution is not None else ""
        technical.append(f"{item.indicator_name}: q={item.normalized_score}{contrib}")
    return LayeredNarrative(
        brief=f"Оценка: {float(assessment.score):.0f} из 100 ({zone}).",
        details=details,
        technical=technical,
    )


def anomalies_narrative(anomalies) -> LayeredNarrative:
    if anomalies is None:
        return LayeredNarrative(brief="Поиск аномалий не запускался.", details=[], technical=[])
    if anomalies.status != ProcedureStatus.OK:
        return LayeredNarrative(
            brief=anomalies.message or "Аномалии не рассчитаны.",
            details=["Процедура пропускается, если наблюдений меньше заданного минимума."],
            technical=[anomalies.method or "", anomalies.message or ""],
        )
    items = anomalies.items or []
    if not items:
        return LayeredNarrative(
            brief="Статистических выбросов не найдено.",
            details=["Метод отмечает только сильные отклонения от типичного уровня ряда."],
            technical=[anomalies.method or "robust_z"],
        )
    by_code: dict[str, int] = {}
    for item in items:
        by_code[item.indicator_name] = by_code.get(item.indicator_name, 0) + 1
    top = ", ".join(f"{name} ({count})" for name, count in sorted(by_code.items(), key=lambda kv: -kv[1])[:5])
    examples = [
        f"«{item.indicator_name}» в {item.period_start}: факт {item.value}, типичный уровень {item.baseline}."
        for item in items[:8]
    ]
    return LayeredNarrative(
        brief=f"Обнаружено выбросов: {len(items)}. Чаще затронуты: {top}.",
        details=examples,
        technical=[
            f"Метод: {anomalies.method or 'robust_z'}.",
            "Сравнение с медианой (или средним) ряда.",
        ],
    )


def correlation_narrative(correlation) -> LayeredNarrative:
    if correlation is None:
        return LayeredNarrative(brief="Корреляции не запускались.", details=[], technical=[])
    if correlation.status != ProcedureStatus.OK:
        return LayeredNarrative(
            brief=correlation.message or "Корреляции не рассчитаны.",
            details=["Нужно достаточно совместных наблюдений у пары показателей."],
            technical=[correlation.message or ""],
        )
    pairs = [p for p in (correlation.pairs or []) if p.coefficient is not None]
    pairs.sort(key=lambda p: abs(p.coefficient), reverse=True)
    pos = [p for p in pairs if p.coefficient >= 0.7][:5]
    neg = [p for p in pairs if p.coefficient <= -0.7][:5]
    details = [
        "Положительный коэффициент: ряды чаще движутся в одну сторону. Отрицательный — в разные.",
    ]
    if pos:
        details.append("Сильные прямые связи: " + "; ".join(f"{p.indicator_a} и {p.indicator_b} ({p.coefficient:.2f})" for p in pos) + ".")
    if neg:
        details.append("Сильные обратные связи: " + "; ".join(f"{p.indicator_a} и {p.indicator_b} ({p.coefficient:.2f})" for p in neg) + ".")
    if not pos and not neg:
        details.append("Пар с |r| ≥ 0,7 в выбранном интервале нет.")
    return LayeredNarrative(
        brief="Корреляции описывают совместное движение рядов.",
        details=details,
        technical=[
            "Коэффициент Пирсона, пропуски исключаются попарно.",
            f"Пар в ответе: {len(pairs)}.",
        ],
    )


def clustering_narrative(clustering) -> LayeredNarrative:
    if clustering is None:
        return LayeredNarrative(brief="Кластеризация не запускалась.", details=[], technical=[])
    if clustering.status != ProcedureStatus.OK or not clustering.clusters:
        return LayeredNarrative(
            brief=clustering.message or "Группы периодов не построены.",
            details=["Метод нуждается в нескольких периодах и различимых сочетаниях показателей."],
            technical=[str(clustering.metrics or {}), clustering.message or ""],
        )
    sizes = ", ".join(f"группа {c.cluster}: {c.size}" for c in clustering.clusters)
    details = [
        f"Периоды разделены на {len(clustering.clusters)} группы ({sizes}).",
        "Номер группы не означает «кризис» или «норму». Сравнивайте центры групп.",
    ]
    for cluster in clustering.clusters:
        if cluster.centroid:
            parts = [f"{code}={value}" for code, value in list(cluster.centroid.items())[:8]]
            details.append(f"Центр группы {cluster.cluster}: " + ", ".join(parts) + ".")
    technical = [f"{k}={v}" for k, v in (clustering.metrics or {}).items()]
    return LayeredNarrative(
        brief=f"Выделено групп периодов: {len(clustering.clusters)}.",
        details=details,
        technical=technical or ["k-средних после масштабирования показателей."],
    )


def forecast_narrative(forecast) -> LayeredNarrative:
    if forecast is None:
        return LayeredNarrative(brief="Прогноз не запускался.", details=[], technical=[])
    if forecast.status != ProcedureStatus.OK or not forecast.series:
        return LayeredNarrative(
            brief=forecast.message or "Прогноз не построен.",
            details=["Нужно не менее четырёх конечных наблюдений."],
            technical=[forecast.message or ""],
        )
    details = [
        "Сплошная линия — факты, пунктир — прогноз.",
    ]
    for series in forecast.series[:6]:
        if not series.points:
            continue
        first, last = series.points[0], series.points[-1]
        if last.value > first.value:
            direction = "точечные значения внутри горизонта выше начального шага прогноза"
        elif last.value < first.value:
            direction = "точечные значения внутри горизонта ниже начального шага прогноза"
        else:
            direction = "существенного наклона внутри горизонта не видно"
        details.append(f"{series.indicator}: горизонт {len(series.points)} шаг(ов); {direction}.")
    return LayeredNarrative(
        brief=f"Прогноз построен для {len(forecast.series)} показателей.",
        details=details,
        technical=["Простое экспоненциальное сглаживание (SimpleExpSmoothing)."],
    )
