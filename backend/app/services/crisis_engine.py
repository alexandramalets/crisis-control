"""Детерминированные правила проблем, предупреждений и рекомендаций. Без выдуманных чисел."""

from __future__ import annotations


RECO_LIMIT = "Предложение по правилу: что проверить по сработавшей проблеме."


def last_prev(series: list[float | None]) -> tuple[float | None, float | None]:
    finite = [float(v) for v in series if v is not None]
    if not finite:
        return None, None
    if len(finite) == 1:
        return finite[-1], None
    return finite[-1], finite[-2]


def worsening(last: float | None, prev: float | None, direction: str) -> bool:
    if last is None or prev is None:
        return False
    if direction == "higher_better":
        return last < prev
    if direction == "lower_better":
        return last > prev
    return False


def pct_change(last: float | None, prev: float | None) -> float | None:
    if last is None or prev in (None, 0):
        return None
    return 100.0 * (last - prev) / abs(prev)


def build_findings(*, values: dict[str, list], directions: dict[str, str],
                   ratios: list[dict], period: str | None) -> list[dict]:
    findings = []

    def pair(code: str):
        return last_prev(values.get(code) or [])

    def need(*codes: str) -> bool:
        return all(last_prev(values.get(c) or [])[0] is not None for c in codes)

    cash_l, cash_p = pair("cash")
    pay_l, pay_p = pair("payables")
    rec_l, rec_p = pair("receivables")
    rev_l, rev_p = pair("revenue")
    profit_l, profit_p = pair("profit")
    cogs_l, cogs_p = pair("cogs")
    cf_l, cf_p = pair("cf_operating")
    ratio_map = {item["code"]: item for item in ratios}
    cr = ratio_map.get("current_ratio") or {}
    autonomy = ratio_map.get("autonomy") or {}
    ros = ratio_map.get("ros") or {}
    dte = ratio_map.get("debt_to_equity") or {}

    if need("cash", "payables"):
        conds = [
            worsening(cash_l, cash_p, "higher_better"),
            worsening(pay_l, pay_p, "lower_better"),
        ]
        extra = cr.get("last_value") is not None and cr.get("pct_change") is not None and cr["pct_change"] < 0
        if all(conds) or (sum(conds) == 1 and extra):
            findings.append(_finding(
                "solvency_pressure", "Проблема платёжеспособности",
                "Снижение денежных средств и/или рост краткосрочных обязательств"
                + (" при ухудшении текущей ликвидности" if extra else "") + ".",
                "high" if all(conds) and extra else "warning",
                "confirmed" if all(conds) else "hypothesis",
                period,
                {"cash": cash_l, "payables": pay_l, "current_ratio": cr.get("last_value")},
                ["cash", "payables"] + (["current_ratio"] if extra else []),
            ))
        elif sum(conds) == 1:
            findings.append(_finding(
                "solvency_pressure", "Проблема платёжеспособности",
                "Наблюдается только часть признаков. Для подтверждения не хватает согласованного движения показателей.",
                "info", "insufficient", period,
                {"cash": cash_l, "payables": pay_l}, ["cash", "payables"],
            ))

    if need("receivables"):
        rec_worse = worsening(rec_l, rec_p, "lower_better")
        turnover = ratio_map.get("receivables_turnover") or {}
        overdue = pair("overdue_receivables")[0]
        if rec_worse and (turnover.get("pct_change") or 0) < 0:
            findings.append(_finding(
                "settlements", "Проблема расчётов с контрагентами",
                "Рост дебиторской задолженности сопровождается снижением оборачиваемости.",
                "warning", "confirmed" if overdue is None else "hypothesis", period,
                {"receivables": rec_l, "turnover": turnover.get("last_value"), "overdue": overdue},
                ["receivables", "receivables_turnover"],
            ))
        elif rec_worse:
            findings.append(_finding(
                "settlements", "Проблема расчётов с контрагентами",
                "Рост дебиторской задолженности. Оборачиваемость не подтверждена — гипотеза, не доказанный срыв расчётов.",
                "info", "hypothesis", period, {"receivables": rec_l}, ["receivables"],
            ))

    if need("revenue", "profit"):
        if worsening(rev_l, rev_p, "higher_better") and worsening(profit_l, profit_p, "higher_better"):
            cogs_note = worsening(cogs_l, cogs_p, "lower_better")
            findings.append(_finding(
                "profitability", "Проблема рентабельности",
                "Одновременное снижение выручки и прибыли"
                + (" при росте себестоимости" if cogs_note else "") + ".",
                "high" if cogs_note or (ros.get("pct_change") or 0) < 0 else "warning",
                "confirmed" if ros.get("last_value") is not None else "hypothesis",
                period,
                {"revenue": rev_l, "profit": profit_l, "ros": ros.get("last_value")},
                ["revenue", "profit"],
            ))

    if need("equity") or autonomy.get("last_value") is not None:
        auto_down = (autonomy.get("pct_change") or 0) < 0
        dte_up = (dte.get("pct_change") or 0) > 0
        if auto_down and dte_up:
            findings.append(_finding(
                "stability", "Проблема финансовой устойчивости",
                "Снижение автономии сочетается с ростом отношения долга к капиталу.",
                "high", "confirmed", period,
                {"autonomy": autonomy.get("last_value"), "debt_to_equity": dte.get("last_value")},
                ["autonomy", "debt_to_equity"],
            ))
        elif auto_down or dte_up:
            findings.append(_finding(
                "stability", "Проблема финансовой устойчивости",
                "Есть отдельные признаки роста долговой нагрузки. Полный набор коэффициентов не подтверждён.",
                "info", "insufficient", period,
                {"autonomy": autonomy.get("last_value"), "debt_to_equity": dte.get("last_value")},
                ["autonomy"],
            ))

    if need("cf_operating") and worsening(cf_l, cf_p, "higher_better"):
        findings.append(_finding(
            "cashflow", "Ослабление операционного денежного потока",
            "Операционный поток снизился относительно предыдущего периода.",
            "warning", "hypothesis", period, {"cf_operating": cf_l}, ["cf_operating"],
        ))
    return findings


def build_alerts(*, trends: list[dict], plans: dict[str, float], norms: dict[str, float],
                 thresholds: dict[str, tuple[float | None, float | None]],
                 directions: dict[str, str], period: str | None) -> list[dict]:
    alerts = []
    seen = set()
    for item in trends:
        code = item["indicator"]
        key_base = (code, item.get("last_period") or period)
        consecutive = int(item.get("consecutive_worsening") or 0)
        last = item.get("last_value")
        direction = directions.get(code) or item.get("impact_direction")
        if consecutive >= 3 and item.get("favorable") is False:
            level = "critical" if consecutive >= 6 else "high" if consecutive >= 4 else "warning"
            alerts.append(_alert(
                code, level, "persistent_worsening",
                f"Непрерывное ухудшение «{code}» на протяжении {consecutive} периодов.",
                "Правило: серия изменений против направления улучшения показателя.",
                "Проверить причины изменения ряда и сопоставить с планом.",
                item.get("last_period") or period,
            ))
        plan = plans.get(code)
        if last is not None and plan not in (None, 0):
            gap = 100.0 * (last - plan) / abs(plan)
            bad = (gap < 0 and direction == "higher_better") or (gap > 0 and direction == "lower_better")
            if bad and abs(gap) >= 10:
                alerts.append(_alert(
                    code, "high" if abs(gap) >= 20 else "warning", "plan_deviation",
                    f"Отклонение факта от плана по «{code}»: {gap:.1f}%.",
                    "Сравнение последнего значения с планом организации.",
                    "Разобрать отклонение от плана и при необходимости скорректировать мероприятие.",
                    item.get("last_period") or period,
                ))
        low, high = thresholds.get(code, (None, None))
        if last is not None and low is not None and last < low and direction == "higher_better":
            alerts.append(_alert(
                code, "critical", "threshold_breach",
                f"«{code}» ниже нижней границы {low}.",
                "Порог задан в профиле организации, не отраслевой константой системы.",
                "Проверить исходные данные и устойчивость показателя.",
                item.get("last_period") or period,
            ))
        if last is not None and high is not None and last > high and direction == "lower_better":
            alerts.append(_alert(
                code, "critical", "threshold_breach",
                f"«{code}» выше верхней границы {high}.",
                "Порог задан в профиле организации.",
                "Проверить допустимость уровня показателя.",
                item.get("last_period") or period,
            ))
        # near bound 10%
        if last is not None and low is not None and direction == "higher_better" and low != 0:
            if 0 < (last - low) / abs(low) <= 0.1:
                alerts.append(_alert(
                    code, "info", "near_threshold",
                    f"«{code}» приближается к нижней границе.",
                    "Расстояние до порога не более 10%.",
                    "Наблюдать показатель на следующем периоде.",
                    item.get("last_period") or period,
                ))
        seen.add(key_base)
    # unique by rule+indicator+period handled in DB
    return alerts


def recommendations_for(findings: list[dict]) -> list[dict]:
    catalog = {
        "solvency_pressure": {
            "title": "Контроль ликвидности и краткосрочных обязательств",
            "actions": "Разобрать структуру оборотного капитала и сроки погашения краткосрочных обязательств, "
                       "сопоставить платежи и поступления.",
            "expected": "Понять, устойчив ли разрыв ликвидности или это разовый сдвиг.",
            "priority": "high",
        },
        "settlements": {
            "title": "Контроль расчётов с дебиторами",
            "actions": "Проанализировать сроки оплаты, сегменты задолженности и дисциплину контрагентов.",
            "expected": "Выявить зависшие суммы и возможные меры по ускорению оборота.",
            "priority": "medium",
        },
        "profitability": {
            "title": "Разбор структуры продаж и затрат",
            "actions": "Сопоставить динамику выручки, прибыли и себестоимости; проверить разовые эффекты.",
            "expected": "Отделить падение маржи от эффекта объёма.",
            "priority": "high",
        },
        "stability": {
            "title": "Оценка структуры капитала",
            "actions": "Проверить долю заёмных средств и покрытие собственным капиталом.",
            "expected": "Понять, растёт ли зависимость от внешнего финансирования.",
            "priority": "high",
        },
        "cashflow": {
            "title": "Платёжный календарь операционного потока",
            "actions": "Сверить операционный поток с графиком платежей и поступлениями.",
            "expected": "Выявить кассовые разрывы без утверждения о банкротстве.",
            "priority": "medium",
        },
    }
    out = []
    for finding in findings:
        if finding["confidence"] == "insufficient":
            continue
        template = catalog.get(finding["code"])
        if not template:
            continue
        out.append({
            "finding_code": finding["code"],
            "title": template["title"],
            "problem": finding["description"],
            "basis": f"Правило «{finding['title']}», уверенность: {finding['confidence']}. "
                     f"Показатели: {', '.join(finding.get('indicators') or [])}.",
            "actions": template["actions"],
            "expected_result": template["expected"],
            "limitations": RECO_LIMIT,
            "priority": template["priority"],
        })
    return out


def _finding(code, title, description, severity, confidence, period, evidence, indicators):
    return {
        "code": code, "title": title, "description": description, "severity": severity,
        "confidence": confidence, "period_label": period, "evidence": evidence,
        "indicators": indicators,
    }


def _alert(code, level, rule, message, basis, action, period):
    return {
        "indicator_code": code, "level": level, "rule_code": rule, "message": message,
        "basis": basis, "action": action, "period_label": period,
    }
