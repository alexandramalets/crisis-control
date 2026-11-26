import hashlib
import json
from collections import Counter
from datetime import date

from sqlalchemy.orm import Session

from app.models import Dataset, DatasetIssue
from app.models.enums import IssueSeverity
from app.repositories.audit_repository import AuditRepository
from app.repositories.dataset_repository import DatasetRepository
from app.repositories.reference_repository import ReferenceRepository
from app.schemas.common import Page
from app.schemas.dataset import (
    DatasetCreate, DatasetDetail, DatasetIndicatorRead, DatasetIssueRead, DatasetSummary, IndicatorValueRead,
)
from app.services.access import AccessContext
from app.services.errors import ConflictError, NotFoundError, ValidationFailedError
from app.services.organization_service import OrganizationService

NOT_FOUND = "Набор данных не найден"


def canonical_sha256(data: DatasetCreate) -> str:
    """Контрольная сумма значений, не зависящая от порядка элементов запроса (S-15)."""
    rows = sorted(
        [item.indicator_code, item.period_start.isoformat(), item.category or "",
         None if item.value is None else format(item.value.normalize(), "f")]
        for item in data.values
    )
    payload = json.dumps({"granularity": data.granularity.value, "values": rows}, ensure_ascii=False,
                         separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class DatasetService:
    def __init__(self, session: Session):
        self.session = session
        self.datasets = DatasetRepository(session)
        self.reference = ReferenceRepository(session)
        self.audit = AuditRepository(session)

    def get_visible(self, ctx: AccessContext, dataset_id: int) -> Dataset:
        ctx.ensure_analyst()
        dataset = self.datasets.get(dataset_id, ctx.read_scope)
        if dataset is None:
            raise NotFoundError(NOT_FOUND)
        return dataset

    def search(self, ctx: AccessContext, organization_id: int | None, limit: int, offset: int) -> Page[DatasetSummary]:
        ctx.ensure_analyst()
        if organization_id is not None:
            OrganizationService(self.session).get_visible(ctx, organization_id)
        items, total = self.datasets.find(ctx.read_scope, organization_id, limit, offset)
        return Page(items=[DatasetSummary.model_validate(d) for d in items], total=total, limit=limit, offset=offset)

    def detail(self, ctx: AccessContext, dataset_id: int) -> DatasetDetail:
        dataset = self.get_visible(ctx, dataset_id)
        period_from, period_to, periods_count = self.datasets.period_range(dataset.id)
        indicators = [DatasetIndicatorRead(**row) for row in self.datasets.indicator_stats(dataset.id)]
        return DatasetDetail(
            **DatasetSummary.model_validate(dataset).model_dump(),
            source_sha256=dataset.source_sha256,
            period_from=period_from, period_to=period_to, periods_count=periods_count,
            values_count=sum(i.values_count for i in indicators),
            categories=self.datasets.categories(dataset.id),
            indicators=indicators,
            issues=[DatasetIssueRead.model_validate(i) for i in self.datasets.issues(dataset.id)],
        )

    def values(self, ctx: AccessContext, dataset_id: int, indicator_codes: list[str] | None,
               period_from: date | None, period_to: date | None, limit: int, offset: int) -> Page[IndicatorValueRead]:
        dataset = self.get_visible(ctx, dataset_id)
        rows, total = self.datasets.values(dataset.id, indicator_codes, period_from, period_to, limit, offset)
        return Page(items=[IndicatorValueRead(**row) for row in rows], total=total, limit=limit, offset=offset)

    def create(self, ctx: AccessContext, organization_id: int, data: DatasetCreate) -> DatasetDetail:
        organization = OrganizationService(self.session).get_modifiable(ctx, organization_id)
        dataset = self.persist(ctx, organization.id, data)
        self.audit.add(
            "dataset_created", ctx.user_id, "dataset", dataset.id,
            organization_id=organization.id,
        )
        self.session.commit()
        return self.detail(ctx, dataset.id)

    def persist(
        self,
        ctx: AccessContext,
        organization_id: int,
        data: DatasetCreate,
        *,
        source_filename: str | None = None,
        source_sha256: str | None = None,
        extra_issues: list[DatasetIssue] | None = None,
    ) -> Dataset:
        """Пишет набор в текущей транзакции без commit (импорт файла добавляет оригинал)."""
        previous = self.datasets.latest_by_name(organization_id, data.name)
        version_no = 1 if previous is None else previous.version_no + 1

        codes = {item.indicator_code for item in data.values}
        indicators = self.reference.indicators_by_code(codes, ctx.user_id)
        unknown = sorted(codes - indicators.keys())
        if unknown:
            raise ValidationFailedError("Неизвестные коды показателей", details={"unknown_indicators": unknown})

        periods = self.reference.ensure_periods(data.granularity, {item.period_start for item in data.values})
        categories = self.reference.ensure_categories(
            organization_id, {item.category for item in data.values if item.category})

        dataset = self.datasets.add(Dataset(
            organization_id=organization_id, uploaded_by=ctx.user_id, name=data.name,
            source_filename=source_filename,
            source_sha256=source_sha256 or canonical_sha256(data),
            granularity=data.granularity,
            version_no=version_no,
            predecessor_id=None if previous is None else previous.id,
        ))
        self.datasets.add_values([
            {"dataset_id": dataset.id, "indicator_id": indicators[item.indicator_code].id,
             "period_id": periods[item.period_start],
             "category_id": categories[item.category] if item.category else None, "value": item.value}
            for item in data.values
        ])
        if extra_issues is None:
            missing = Counter(item.indicator_code for item in data.values if item.value is None)
            extra_issues = [
                DatasetIssue(severity=IssueSeverity.WARNING, code="missing_values",
                             column_name=code, message=f"Пропущено значений показателя «{code}»: {count}")
                for code, count in sorted(missing.items())
            ]
        for issue in extra_issues:
            issue.dataset_id = dataset.id
        self.datasets.add_issues(extra_issues)
        return dataset

    def delete(self, ctx: AccessContext, dataset_id: int) -> None:
        dataset = self.get_visible(ctx, dataset_id)
        OrganizationService(self.session).get_modifiable(ctx, dataset.organization_id)
        from app.core.config import get_settings
        from app.services.ingest.storage import FileStorage
        FileStorage(get_settings()).delete_dataset_file(dataset.id)
        self.datasets.delete(dataset)
        self.audit.add(
            "dataset_deleted", ctx.user_id, "dataset", dataset_id,
            organization_id=dataset.organization_id,
        )
        self.session.commit()
