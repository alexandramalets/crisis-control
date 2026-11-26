"""Проблемы, предупреждения, рекомендации, мероприятия, сценарии, нормативы."""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    AnalysisAlert, AnalysisFinding, CrisisMeasure, Dataset, Indicator, IndicatorTarget, IndicatorThreshold,
    MeasureEvent, OrganizationAccess, Recommendation, RatioResult, User, WhatIfScenario,
)
from app.models.enums import OrganizationAccessLevel, TargetKind
from app.repositories.audit_repository import AuditRepository
from app.services.access import AccessContext
from app.services.analysis_service import AnalysisService, format_period
from app.services.crisis_engine import build_alerts, build_findings, recommendations_for
from app.services.errors import NotFoundError, PermissionDeniedError, ValidationFailedError
from app.services.organization_service import OrganizationService, _level_value


class GovernanceService:
    def __init__(self, session: Session):
        self.session = session
        self.audit = AuditRepository(session)
        self.orgs = OrganizationService(session)
        self.analyses = AnalysisService(session)

    def _editable(self, ctx: AccessContext, organization_id: int):
        ctx.ensure_analyst()
        return self.orgs.get_modifiable(ctx, organization_id)

    def _visible(self, ctx: AccessContext, organization_id: int):
        ctx.ensure_analyst()
        return self.orgs.get_visible(ctx, organization_id)

    def post_process_run(self, run, dataset: Dataset, envelopes: dict, code_map: dict) -> None:
        trends = []
        env = envelopes.get("trends")
        if env and env.result:
            trends = env.result.get("items") or []
        ratios = []
        env = envelopes.get("ratios")
        if env and env.result:
            ratios = env.result.get("items") or []
        directions = {code: indicator.impact_direction.value for code, indicator in code_map.items()}
        from app.models import Period
        from app.repositories.analysis_repository import AnalysisRepository
        repo = AnalysisRepository(self.session)
        indicator_ids = [ind.id for ind in code_map.values()]
        start = self.session.get(Period, run.period_from_id)
        end = self.session.get(Period, run.period_to_id)
        rows = repo.matrix_rows(dataset.id, indicator_ids, start.start_date, end.start_date)
        by_code: dict[str, dict] = {}
        id_to_code = {ind.id: code for code, ind in code_map.items()}
        for row in rows:
            code = id_to_code.get(row["indicator_id"])
            if not code:
                continue
            by_code.setdefault(code, {})[row["start_date"]] = None if row["value"] is None else float(row["value"])
        starts = sorted({row["start_date"] for row in rows})
        series = {code: [by_code.get(code, {}).get(start) for start in starts] for code in id_to_code.values()}
        period_label = format_period(end.start_date, dataset.granularity) if end else None
        plans, norms, bounds = self._targets(dataset.organization_id)
        findings = build_findings(values=series, directions=directions, ratios=ratios, period=period_label)
        alerts = build_alerts(
            trends=trends, plans=plans, norms=norms, thresholds=bounds,
            directions=directions, period=period_label,
        )
        for item in findings:
            row = AnalysisFinding(
                organization_id=dataset.organization_id, run_id=run.id, code=item["code"],
                title=item["title"], description=item["description"], severity=item["severity"],
                confidence=item["confidence"], period_label=item.get("period_label"),
                evidence=item.get("evidence") or {},
            )
            self.session.add(row)
            self.session.flush()
            item["_id"] = row.id
        existing_alerts = {(a.rule_code, a.indicator_code, a.period_label) for a in self.session.scalars(
            select(AnalysisAlert).where(AnalysisAlert.run_id == run.id)
        )}
        for item in alerts:
            key = (item["rule_code"], item["indicator_code"], item.get("period_label"))
            if key in existing_alerts:
                continue
            self.session.add(AnalysisAlert(
                organization_id=dataset.organization_id, run_id=run.id, **item,
            ))
            existing_alerts.add(key)
        recs = recommendations_for(findings)
        for rec in recs:
            finding_id = next((f["_id"] for f in findings if f["code"] == rec["finding_code"]), None)
            self.session.add(Recommendation(
                organization_id=dataset.organization_id, run_id=run.id, finding_id=finding_id,
                title=rec["title"], problem=rec["problem"], basis=rec["basis"],
                actions=rec["actions"], expected_result=rec["expected_result"],
                limitations=rec["limitations"], priority=rec["priority"],
            ))

    def _targets(self, organization_id: int):
        plans, norms, bounds = {}, {}, {}
        for row in self.session.scalars(
            select(IndicatorTarget).where(IndicatorTarget.organization_id == organization_id)
        ):
            indicator = self.session.get(Indicator, row.indicator_id)
            if indicator is None:
                continue
            if row.kind == TargetKind.PLAN:
                plans[indicator.code] = float(row.value)
            elif row.kind == TargetKind.NORM:
                norms[indicator.code] = float(row.value)
        for row in self.session.scalars(
            select(IndicatorThreshold).where(IndicatorThreshold.organization_id == organization_id)
        ):
            indicator = self.session.get(Indicator, row.indicator_id)
            if indicator is None:
                continue
            bounds[indicator.code] = (
                None if row.lower_bound is None else float(row.lower_bound),
                None if row.upper_bound is None else float(row.upper_bound),
            )
        return plans, norms, bounds

    def list_findings(self, ctx, organization_id: int, run_id: int | None):
        self._visible(ctx, organization_id)
        query = select(AnalysisFinding).where(AnalysisFinding.organization_id == organization_id)
        if run_id:
            query = query.where(AnalysisFinding.run_id == run_id)
        return list(self.session.scalars(query.order_by(AnalysisFinding.id.desc())))

    def list_alerts(self, ctx, organization_id: int, run_id: int | None):
        self._visible(ctx, organization_id)
        query = select(AnalysisAlert).where(AnalysisAlert.organization_id == organization_id)
        if run_id:
            query = query.where(AnalysisAlert.run_id == run_id)
        return list(self.session.scalars(query.order_by(AnalysisAlert.id.desc())))

    def list_recommendations(self, ctx, organization_id: int, run_id: int | None):
        self._visible(ctx, organization_id)
        query = select(Recommendation).where(Recommendation.organization_id == organization_id)
        if run_id:
            query = query.where(Recommendation.run_id == run_id)
        return list(self.session.scalars(query.order_by(Recommendation.id.desc())))

    def update_recommendation(self, ctx, recommendation_id: int, status: str, comment: str | None):
        rec = self.session.get(Recommendation, recommendation_id)
        if rec is None:
            raise NotFoundError("Рекомендация не найдена")
        self._editable(ctx, rec.organization_id)
        if status not in {"accepted", "rejected", "proposed"}:
            raise ValidationFailedError("Недопустимый статус рекомендации")
        rec.status = status
        rec.updated_at = datetime.now(UTC)
        self.audit.add(
            "recommendation_updated", ctx.user_id, "recommendation", rec.id,
            organization_id=rec.organization_id,
        )
        self.session.commit()
        return rec

    def convert_recommendation(self, ctx, recommendation_id: int, due_at: date | None, assignee_id: int | None):
        rec = self.session.get(Recommendation, recommendation_id)
        if rec is None:
            raise NotFoundError("Рекомендация не найдена")
        self._editable(ctx, rec.organization_id)
        rec.status = "converted"
        rec.updated_at = datetime.now(UTC)
        measure = CrisisMeasure(
            organization_id=rec.organization_id, created_by=ctx.user_id, assignee_id=assignee_id,
            run_id=rec.run_id, recommendation_id=rec.id, finding_id=rec.finding_id,
            title=rec.title, description=rec.actions, expected_result=rec.expected_result,
            success_criterion=rec.limitations, priority=rec.priority, status="planned", due_at=due_at,
        )
        self.session.add(measure)
        self.session.flush()
        self.session.add(MeasureEvent(
            measure_id=measure.id, user_id=ctx.user_id, event_type="created_from_recommendation",
        ))
        self.audit.add(
            "measure_created", ctx.user_id, "measure", measure.id,
            organization_id=rec.organization_id,
        )
        self.session.commit()
        self.session.refresh(measure)
        return measure

    def list_measures(self, ctx, organization_id: int):
        self._visible(ctx, organization_id)
        items = list(self.session.scalars(
            select(CrisisMeasure).where(CrisisMeasure.organization_id == organization_id)
            .order_by(CrisisMeasure.id.desc())
        ))
        today = date.today()
        for item in items:
            if item.status in {"planned", "in_progress"} and item.due_at and item.due_at < today:
                item.status = "overdue"
        return items

    def create_measure(self, ctx, organization_id: int, data: dict):
        self._editable(ctx, organization_id)
        assignee_id = data.get("assignee_id")
        if assignee_id:
            self._ensure_member(organization_id, assignee_id)
        measure = CrisisMeasure(
            organization_id=organization_id, created_by=ctx.user_id,
            assignee_id=assignee_id, run_id=data.get("run_id"), finding_id=data.get("finding_id"),
            title=data["title"], description=data.get("description") or data["title"],
            expected_result=data.get("expected_result"), success_criterion=data.get("success_criterion"),
            priority=data.get("priority") or "medium", status="planned",
            due_at=data.get("due_at"), indicator_codes=data.get("indicator_codes") or [],
        )
        self.session.add(measure)
        self.session.flush()
        self.session.add(MeasureEvent(measure_id=measure.id, user_id=ctx.user_id, event_type="created"))
        self.audit.add(
            "measure_created", ctx.user_id, "measure", measure.id,
            organization_id=organization_id,
        )
        self.session.commit()
        self.session.refresh(measure)
        return measure

    def update_measure(self, ctx, measure_id: int, data: dict):
        measure = self.session.get(CrisisMeasure, measure_id)
        if measure is None:
            raise NotFoundError("Мероприятие не найдено")
        self._editable(ctx, measure.organization_id)
        if measure.status == "done" and data.get("status") == "cancelled":
            raise ValidationFailedError("Выполненное мероприятие остаётся в истории")
        previous = measure.status
        for field in ("title", "description", "expected_result", "success_criterion", "actual_result",
                      "priority", "status", "due_at", "assignee_id", "indicator_codes"):
            if field in data and data[field] is not None:
                if field == "assignee_id":
                    self._ensure_member(measure.organization_id, data[field])
                setattr(measure, field, data[field])
        measure.updated_at = datetime.now(UTC)
        self.session.add(MeasureEvent(
            measure_id=measure.id, user_id=ctx.user_id, event_type="updated",
            comment=data.get("comment"), payload={"from": previous, "to": measure.status},
        ))
        self.audit.add(
            "measure_updated", ctx.user_id, "measure", measure.id,
            organization_id=measure.organization_id,
        )
        self.session.commit()
        self.session.refresh(measure)
        return measure

    def delete_measure(self, ctx, measure_id: int) -> None:
        measure = self.session.get(CrisisMeasure, measure_id)
        if measure is None:
            raise NotFoundError("Мероприятие не найдено")
        self._editable(ctx, measure.organization_id)
        organization_id = measure.organization_id
        self.session.delete(measure)
        self.audit.add(
            "measure_deleted", ctx.user_id, "measure", measure_id,
            organization_id=organization_id,
        )
        self.session.commit()

    def measure_events(self, ctx, measure_id: int):
        measure = self.session.get(CrisisMeasure, measure_id)
        if measure is None:
            raise NotFoundError("Мероприятие не найдено")
        self._visible(ctx, measure.organization_id)
        return list(self.session.scalars(
            select(MeasureEvent).where(MeasureEvent.measure_id == measure_id).order_by(MeasureEvent.id)
        ))

    def _ensure_member(self, organization_id: int, user_id: int):
        if self.session.get(User, user_id) is None:
            raise ValidationFailedError("Пользователь не найден")
        row = self.session.get(OrganizationAccess, (organization_id, user_id))
        if row is None:
            raise ValidationFailedError("Назначить можно только сотрудника этой организации")

    def list_targets(self, ctx, organization_id: int):
        self._visible(ctx, organization_id)
        targets = []
        for row in self.session.scalars(
            select(IndicatorTarget).where(IndicatorTarget.organization_id == organization_id)
        ):
            indicator = self.session.get(Indicator, row.indicator_id)
            targets.append({
                "id": row.id,
                "indicator_code": None if indicator is None else indicator.code,
                "kind": row.kind.value if hasattr(row.kind, "value") else str(row.kind),
                "value": row.value,
                "source": row.source,
                "notes": row.notes,
                "valid_from": row.valid_from,
                "valid_to": row.valid_to,
            })
        thresholds = []
        for row in self.session.scalars(
            select(IndicatorThreshold).where(IndicatorThreshold.organization_id == organization_id)
        ):
            indicator = self.session.get(Indicator, row.indicator_id)
            thresholds.append({
                "indicator_code": None if indicator is None else indicator.code,
                "lower_bound": row.lower_bound,
                "upper_bound": row.upper_bound,
                "source": row.source,
                "notes": row.notes,
                "methodology": row.methodology,
            })
        return targets, thresholds

    def upsert_target(self, ctx, organization_id: int, data: dict):
        payload = self._upsert_target(ctx, organization_id, data)
        self.session.commit()
        return payload

    def upsert_threshold(self, ctx, organization_id: int, data: dict):
        payload = self._upsert_threshold(ctx, organization_id, data)
        self.session.commit()
        return payload

    def import_profile_file(self, ctx, organization_id: int, filename: str, content: bytes) -> dict:
        self._editable(ctx, organization_id)
        from app.services.ingest.profile_import import parse_profile_file

        catalog = {item.code: item for item in self.session.scalars(select(Indicator)).all()}
        by_name = {item.name.casefold(): item for item in catalog.values()}
        parsed = parse_profile_file(content, filename)
        applied, skipped = [], []
        for item in parsed["targets"]:
            indicator = _resolve_indicator(catalog, by_name, item)
            if indicator is None:
                skipped.append(item.get("indicator_code") or item.get("name") or "?")
                continue
            item["indicator_code"] = indicator.code
            applied.append(self._upsert_target(ctx, organization_id, item, audit=False))
        for item in parsed["thresholds"]:
            indicator = _resolve_indicator(catalog, by_name, item)
            if indicator is None:
                skipped.append(item.get("indicator_code") or item.get("name") or "?")
                continue
            item["indicator_code"] = indicator.code
            applied.append(self._upsert_threshold(ctx, organization_id, item, audit=False))
        if not applied:
            raise ValidationFailedError("В файле нет распознанных планов или границ")
        self.audit.add(
            "norm_updated", ctx.user_id, "indicator_target", organization_id,
            organization_id=organization_id,
        )
        self.session.commit()
        return {"imported": len(applied), "skipped": skipped}

    def _upsert_target(self, ctx, organization_id: int, data: dict, *, audit: bool = True):
        self._editable(ctx, organization_id)
        indicator = self.session.scalar(select(Indicator).where(Indicator.code == data["indicator_code"]))
        if indicator is None:
            raise ValidationFailedError("Показатель не найден")
        kind = TargetKind(data["kind"])
        row = self.session.scalar(
            select(IndicatorTarget).where(
                IndicatorTarget.organization_id == organization_id,
                IndicatorTarget.indicator_id == indicator.id,
                IndicatorTarget.kind == kind,
                IndicatorTarget.period_id.is_(None),
            )
        )
        if row is None:
            row = IndicatorTarget(
                organization_id=organization_id, indicator_id=indicator.id, kind=kind,
            )
            self.session.add(row)
        row.value = data["value"]
        row.source = data.get("source")
        row.notes = data.get("notes")
        row.valid_from = data.get("valid_from")
        row.valid_to = data.get("valid_to")
        if audit:
            self.audit.add(
                "norm_updated", ctx.user_id, "indicator_target", organization_id,
                organization_id=organization_id,
            )
        self.session.flush()
        return {
            "id": row.id, "indicator_code": indicator.code,
            "kind": kind.value, "value": row.value, "source": row.source, "notes": row.notes,
            "valid_from": row.valid_from, "valid_to": row.valid_to,
        }

    def _upsert_threshold(self, ctx, organization_id: int, data: dict, *, audit: bool = True):
        self._editable(ctx, organization_id)
        indicator = self.session.scalar(select(Indicator).where(Indicator.code == data["indicator_code"]))
        if indicator is None:
            raise ValidationFailedError("Показатель не найден")
        if data.get("lower_bound") is None and data.get("upper_bound") is None:
            raise ValidationFailedError("Укажите нижнюю или верхнюю границу")
        existing = self.session.get(IndicatorThreshold, (organization_id, indicator.id))
        if existing is None:
            existing = IndicatorThreshold(organization_id=organization_id, indicator_id=indicator.id)
            self.session.add(existing)
        existing.lower_bound = data.get("lower_bound")
        existing.upper_bound = data.get("upper_bound")
        existing.source = data.get("source")
        existing.notes = data.get("notes")
        existing.methodology = data.get("methodology")
        if audit:
            self.audit.add(
                "threshold_updated", ctx.user_id, "indicator_threshold", organization_id,
                organization_id=organization_id,
            )
        self.session.flush()
        return {
            "indicator_code": indicator.code,
            "lower_bound": existing.lower_bound,
            "upper_bound": existing.upper_bound,
            "source": existing.source,
            "notes": existing.notes,
            "methodology": existing.methodology,
        }

    def create_scenario(self, ctx, organization_id: int, data: dict):
        self._editable(ctx, organization_id)
        run = self.analyses.ensure_visible(ctx, data["base_run_id"])
        if run["organization_id"] != organization_id:
            raise PermissionDeniedError("Исследование принадлежит другой организации")
        adjustments = [
            {"indicator_code": item["indicator_code"], "percent_change": float(item["percent_change"])}
            for item in (data.get("adjustments") or [])
        ]
        payload = self._simulate(ctx, data["base_run_id"], adjustments)
        scenario = WhatIfScenario(
            organization_id=organization_id, created_by=ctx.user_id, base_run_id=data["base_run_id"],
            name=data["name"], description=data.get("description"),
            adjustments=adjustments, result=payload,
        )
        self.session.add(scenario)
        self.session.flush()
        self.audit.add(
            "scenario_created", ctx.user_id, "scenario", scenario.id,
            organization_id=organization_id,
        )
        self.session.commit()
        self.session.refresh(scenario)
        return scenario

    def _simulate(self, ctx, run_id: int, adjustments: list[dict]) -> dict:
        summary = self.analyses.ensure_visible(ctx, run_id)
        from app.models import AnalysisRun, Period
        run = self.session.get(AnalysisRun, run_id)
        dataset = self.session.get(Dataset, summary["dataset_id"])
        start = self.session.get(Period, run.period_from_id)
        end = self.session.get(Period, run.period_to_id)
        ids = [item.indicator_id for item in run.indicators]
        rows = self.analyses.analyses.matrix_rows(dataset.id, ids, start.start_date, end.start_date)
        starts = sorted({row["start_date"] for row in rows})
        labels = [format_period(item, dataset.granularity) for item in starts]
        by_ind = {}
        for row in rows:
            by_ind.setdefault(row["indicator_id"], {})[row["start_date"]] = (
                None if row["value"] is None else float(row["value"])
            )
        adj_map = {a["indicator_code"]: float(a["percent_change"]) for a in adjustments}
        series = []
        for link in run.indicators:
            indicator = self.session.get(Indicator, link.indicator_id)
            values = [by_ind.get(indicator.id, {}).get(start) for start in starts]
            if indicator.code in adj_map and values:
                factor = 1 + adj_map[indicator.code] / 100.0
                values = [None if v is None else round(v * factor, 6) for v in values]
            item = {
                "code": indicator.code, "values": values,
                "impact_direction": indicator.impact_direction.value, "weight": float(link.weight),
            }
            series.append(item)
        payload = {
            "random_state": run.random_state, "periods": labels, "indicators": series,
            "procedures": ["ratios", "assessment", "trends"],
        }
        try:
            response = self.analyses.client.analyze(payload)
            procedures = {name: env.model_dump() for name, env in response.procedures.items()}
        except Exception as exc:
            return {"error": str(exc), "disclaimer": "Сценарий не рассчитан."}
        return {
            "disclaimer": "Условный расчёт. Исходные данные не изменены.",
            "procedures": procedures,
        }

    def list_scenarios(self, ctx, organization_id: int):
        self._visible(ctx, organization_id)
        return list(self.session.scalars(
            select(WhatIfScenario).where(WhatIfScenario.organization_id == organization_id)
            .order_by(WhatIfScenario.id.desc())
        ))

    def compare_runs(self, ctx, run_id: int, other_id: int) -> dict:
        a = self.analyses.results(ctx, run_id)
        b = self.analyses.results(ctx, other_id)
        if a.run.organization_id != b.run.organization_id:
            raise PermissionDeniedError("Сравнивать можно только исследования одной организации")
        same_dataset = a.run.dataset_id == b.run.dataset_id
        same_period = a.run.period_from == b.run.period_from and a.run.period_to == b.run.period_to
        same_version = a.run.analytics_service_version == b.run.analytics_service_version
        comparable = same_dataset and same_period
        left = _compare_side(a)
        right = _compare_side(b)
        delta = None
        if comparable:
            delta = {
                "score": _diff(left.get("score"), right.get("score")),
                "history_score": _diff(left.get("history_score"), right.get("history_score")),
                "compliance_score": _diff(left.get("compliance_score"), right.get("compliance_score")),
                "findings": (left.get("findings") or 0) - (right.get("findings") or 0),
                "alerts": (left.get("alerts") or 0) - (right.get("alerts") or 0),
                "anomalies": (left.get("anomalies") or 0) - (right.get("anomalies") or 0),
                "worsening_trends": (left.get("worsening_trends") or 0) - (right.get("worsening_trends") or 0),
            }
        note = None
        if not comparable:
            reasons = []
            if not same_dataset:
                reasons.append("разные версии или наборы данных")
            if not same_period:
                reasons.append("разные анализируемые периоды")
            if not same_version:
                reasons.append("разные версии аналитического сервиса")
            note = "Сравнение оценок некорректно: " + ", ".join(reasons) + "."
        elif not same_version:
            note = "Период и набор совпадают, но версии расчёта различаются. Сравнение ориентировочное."
        return {"left": left, "right": right, "comparable": comparable, "delta": delta, "note": note}

    def audit_feed(self, ctx, organization_id: int):
        self._visible(ctx, organization_id)
        from app.models import AuditLog
        from sqlalchemy import or_
        member_ids = list(self.session.scalars(
            select(OrganizationAccess.user_id).where(OrganizationAccess.organization_id == organization_id)
        ))
        condition = AuditLog.organization_id == organization_id
        if member_ids:
            condition = or_(
                condition,
                (AuditLog.organization_id.is_(None)) & (AuditLog.user_id.in_(member_ids)),
            )
        rows = list(self.session.scalars(
            select(AuditLog).where(condition)
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(40)
        ))
        return [
            {
                "id": row.id, "user_id": row.user_id, "organization_id": row.organization_id,
                "action": row.action, "object_type": row.object_type, "object_id": row.object_id,
                "created_at": row.created_at,
            }
            for row in rows
        ]


def _resolve_indicator(catalog: dict, by_name: dict, item: dict):
    from app.services.ingest.indicators import SYNONYMS, normalize_label

    code = (item.get("indicator_code") or "").strip()
    name = (item.get("name") or "").strip()
    for key in (code, code.casefold()):
        if key and key in catalog:
            return catalog[key]
    for label in (code, name):
        if not label:
            continue
        found = by_name.get(label.casefold())
        if found is not None:
            return found
        synonym = SYNONYMS.get(normalize_label(label))
        if synonym and synonym in catalog:
            return catalog[synonym]
    return None


def _compare_side(results) -> dict:
    assessment = results.assessment
    trends = results.trends.items if results.trends else []
    return {
        "id": results.run.id,
        "score": assessment.score if assessment else None,
        "history_score": assessment.history_score if assessment else None,
        "compliance_score": assessment.compliance_score if assessment else None,
        "completeness": assessment.completeness if assessment else None,
        "dataset": results.run.dataset_name,
        "dataset_id": results.run.dataset_id,
        "period_from": str(results.run.period_from),
        "period_to": str(results.run.period_to),
        "version": results.run.analytics_service_version,
        "findings": len(results.findings or []),
        "alerts": len(results.alerts or []),
        "anomalies": len(results.anomalies.items) if results.anomalies else 0,
        "worsening_trends": sum(1 for item in trends if item.consecutive_worsening),
        "ratios": len(results.ratios.items) if results.ratios else 0,
    }


def _diff(left, right):
    if left is None or right is None:
        return None
    return float(left) - float(right)
