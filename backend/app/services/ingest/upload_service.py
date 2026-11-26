"""Оркестрация загрузки: просмотр, проверка качества, импорт в PostgreSQL."""

import hashlib
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import DatasetFile, DatasetIssue
from app.models.enums import IssueSeverity, PeriodGranularity
from app.repositories.audit_repository import AuditRepository
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.reference_repository import ReferenceRepository
from app.schemas.dataset import (
    DatasetCreate, DatasetDetail, DatasetImportRequest, IndicatorValueIn,
)
from app.services.access import AccessContext
from app.services.dataset_service import DatasetService
from app.services.errors import ValidationFailedError
from app.services.ingest.file_reader import read_table
from app.services.ingest.indicators import IndicatorCatalog
from app.services.ingest.preprocessor import inspect_table, parse_table, quality_summary
from app.services.ingest.storage import FileStorage
from app.services.ingest.templates import csv_template, xlsx_template
from app.services.ingest.types import ParseResult, Table
from app.services.organization_service import OrganizationService


class UploadService:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings
        self.storage = FileStorage(settings)
        self.reference = ReferenceRepository(session)
        self.datasets = DatasetRepository(session)
        self.audit = AuditRepository(session)

    def catalog(self, user_id: int) -> IndicatorCatalog:
        return IndicatorCatalog(self.reference.list_indicators(user_id))

    def preview(self, ctx: AccessContext, filename: str, content: bytes) -> dict:
        ctx.ensure_analyst()
        table = read_table(content, filename, max_bytes=self.settings.upload_max_bytes,
                           max_rows=self.settings.upload_max_rows)
        inspection = inspect_table(table, self.catalog(ctx.user_id))
        digest = hashlib.sha256(content).hexdigest()
        staging = self.storage.put_staging(ctx.user_id, filename, content, digest)
        if not inspection["suggested_indicators"] and inspection["format"] == "wide":
            inspection["blocking_message"] = (
                "В файле нет пригодных числовых столбцов с известными показателями"
            )
        return {
            "staging_id": str(staging.id),
            "original_filename": staging.original_filename,
            "size_bytes": staging.size_bytes,
            "sha256": staging.sha256,
            **inspection,
        }

    def validate(self, ctx: AccessContext, staging_id: uuid.UUID, period_column: str | None,
                 indicator_columns: list[str] | None, category_column: str | None,
                 granularity: PeriodGranularity | None) -> dict:
        ctx.ensure_analyst()
        table, result = self._parse_staging(
            ctx, staging_id, period_column, indicator_columns, category_column, granularity)
        return quality_summary(result, table)

    def import_file(self, ctx: AccessContext, organization_id: int,
                    request: DatasetImportRequest) -> DatasetDetail:
        ctx.ensure_analyst()
        organization = OrganizationService(self.session).get_modifiable(ctx, organization_id)

        staging_ids = request.staging_ids or [request.staging_id]
        merged: dict[tuple, IndicatorValueIn] = {}
        filenames: list[str] = []
        extras = []
        last_result = None
        last_table = None
        for staging_id in staging_ids:
            staging, content = self.storage.get_staging(staging_id, ctx.user_id)
            table, result = self._parse_bytes(
                ctx, staging.original_filename, content,
                request.period_column, request.indicator_columns, request.category_column, request.granularity,
            )
            last_result, last_table = result, table
            filenames.append(staging.original_filename)
            extras.extend(_stored_issues(result))
            if not result.ready_for_save:
                raise ValidationFailedError(
                    "Файл не прошёл проверку и не сохранён",
                    details=quality_summary(result, table),
                )
            for cell in result.cells:
                key = (cell.indicator_code, cell.period_start, cell.category)
                incoming = IndicatorValueIn(
                    indicator_code=cell.indicator_code, period_start=cell.period_start,
                    category=cell.category, value=cell.value,
                )
                previous = merged.get(key)
                if previous is not None and previous.value != incoming.value:
                    extras.append(DatasetIssue(
                        severity=IssueSeverity.WARNING, code="merged_overlap",
                        column_name=cell.indicator_code,
                        message=(
                            f"Период {cell.period_start}: «{cell.indicator_code}» задан в нескольких файлах, "
                            "оставлено последнее значение"
                        ),
                    ))
                merged[key] = incoming

        if request.merge_previous:
            previous_ds = self.datasets.latest_by_name(organization.id, request.name)
            if previous_ds is not None:
                rows, _total = self.datasets.values(previous_ds.id, None, None, None, 100_000, 0)
                for row in rows:
                    key = (row["indicator_code"], row["period_start"], row["category"])
                    if key not in merged:
                        merged[key] = IndicatorValueIn(
                            indicator_code=row["indicator_code"], period_start=row["period_start"],
                            category=row["category"], value=row["value"],
                        )
                extras.append(DatasetIssue(
                    severity=IssueSeverity.WARNING, code="merged_previous",
                    message=f"Объединено с предыдущей версией набора «{request.name}»",
                ))

        if last_result is None:
            raise ValidationFailedError("Нет файлов для сохранения")

        dataset = DatasetService(self.session).persist(
            ctx, organization.id, DatasetCreate(
                name=request.name, granularity=last_result.granularity,
                values=list(merged.values()),
            ),
            source_filename="; ".join(filenames)[:240],
            source_sha256=staging.sha256,
            extra_issues=extras,
        )
        try:
            ciphertext, nonce = self.storage.store_encrypted(dataset.id, content)
            self.session.add(DatasetFile(dataset_id=dataset.id, ciphertext=ciphertext, nonce=nonce, key_version=1))
            self.audit.add(
                "dataset_imported", ctx.user_id, "dataset", dataset.id,
                organization_id=dataset.organization_id,
            )
            self.session.commit()
        except Exception:
            self.storage.delete_dataset_file(dataset.id)
            self.session.rollback()
            raise
        for staging_id in staging_ids:
            self.storage.drop_staging(staging_id)
        return DatasetService(self.session).detail(ctx, dataset.id)

    def import_demo(self, ctx: AccessContext, organization_id: int) -> DatasetDetail:
        """Синтетический набор из пакета приложения. Не подставляется без явного запроса."""
        path = Path(__file__).resolve().parents[2] / "assets" / "demo_indicators.csv"
        if not path.is_file():
            raise ValidationFailedError("Демонстрационный файл не найден в установке сервера")
        content = path.read_bytes()
        name = "Демонстрационный набор"
        preview = self.preview(ctx, "demo_indicators.csv", content)
        columns = [item["column"] for item in preview.get("suggested_indicators") or []]
        if not columns:
            raise ValidationFailedError("В демонстрационном файле нет распознанных показателей")
        return self.import_file(ctx, organization_id, DatasetImportRequest(
            staging_id=preview["staging_id"],
            name=name,
            period_column=preview.get("suggested_period_column") or "period",
            indicator_columns=columns,
        ))

    def template(self, ctx: AccessContext, fmt: str) -> tuple[bytes, str, str]:
        ctx.ensure_analyst()
        indicators = self.reference.list_indicators(ctx.user_id)
        system = [i for i in indicators if i.owner_id is None]
        if fmt == "xlsx":
            return xlsx_template(system), "template.xlsx", \
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return csv_template(system), "template.csv", "text/csv; charset=utf-8"

    def schema(self, ctx: AccessContext, dataset_id: int) -> dict:
        detail = DatasetService(self.session).detail(ctx, dataset_id)
        return {
            "dataset_id": detail.id,
            "name": detail.name,
            "source_filename": detail.source_filename,
            "granularity": detail.granularity.value,
            "period": {
                "role": "time",
                "from": detail.period_from,
                "to": detail.period_to,
                "count": detail.periods_count,
                "usable_for_time_analysis": (detail.periods_count or 0) >= 3,
            },
            "indicators": [
                {"code": i.code, "name": i.name, "unit": i.unit, "values_count": i.values_count,
                 "missing_count": i.missing_count}
                for i in detail.indicators
            ],
            "categories": detail.categories,
        }

    def quality(self, ctx: AccessContext, dataset_id: int) -> dict:
        detail = DatasetService(self.session).detail(ctx, dataset_id)
        missing = sum(i.missing_count for i in detail.indicators)
        return {
            "dataset_id": detail.id,
            "ready_for_analysis": True,
            "values_count": detail.values_count,
            "missing_count": missing,
            "indicators": [i.code for i in detail.indicators],
            "granularity": detail.granularity.value,
            "period_from": detail.period_from,
            "period_to": detail.period_to,
            "distinct_periods": detail.periods_count,
            "time_analysis": {
                "possible": (detail.periods_count or 0) >= 3,
                "distinct_periods": detail.periods_count,
                "granularity": detail.granularity.value,
                "reason": None if (detail.periods_count or 0) >= 3
                else "Для анализа динамики нужно не менее 3 различных периодов",
            },
            "issues": [i.model_dump() for i in detail.issues],
        }

    def _parse_staging(self, ctx, staging_id, period_column, indicator_columns, category_column, granularity):
        staging, content = self.storage.get_staging(staging_id, ctx.user_id)
        return self._parse_bytes(ctx, staging.original_filename, content,
                                 period_column, indicator_columns, category_column, granularity)

    def _parse_bytes(self, ctx: AccessContext, filename: str, content: bytes,
                     period_column, indicator_columns, category_column, granularity) -> tuple[Table, ParseResult]:
        table = read_table(content, filename, max_bytes=self.settings.upload_max_bytes,
                           max_rows=self.settings.upload_max_rows)
        result = parse_table(
            table, self.catalog(ctx.user_id),
            period_column=period_column, indicator_columns=indicator_columns,
            category_column=category_column, granularity=granularity,
        )
        return table, result


def _stored_issues(result: ParseResult) -> list[DatasetIssue]:
    """В БД — сводка, не каждая ячейка: исходный файл хранится отдельно."""
    issues: list[DatasetIssue] = []
    missing = Counter(cell.indicator_code for cell in result.cells if cell.value is None)
    for code, count in sorted(missing.items()):
        issues.append(DatasetIssue(
            severity=IssueSeverity.WARNING, code="missing_values", column_name=code,
            message=f"Пропущено значений показателя «{code}»: {count}",
        ))
    for item in result.transformations:
        issues.append(DatasetIssue(
            severity=IssueSeverity.WARNING, code=item.code, column_name=item.column_name,
            message=item.message,
        ))
    extras = [item for item in result.issues
              if item.severity == IssueSeverity.WARNING and item.code != "missing_values"]
    for item in extras[:50]:
        issues.append(DatasetIssue(
            severity=item.severity, code=item.code, row_number=item.row_number,
            column_name=item.column_name, message=item.message,
        ))
    return issues
