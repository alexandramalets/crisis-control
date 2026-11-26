from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, File, Query, Response, UploadFile, status

from app.api.deps import Access, AppSettings, DbSession, Pagination, error_responses
from app.schemas.common import Page
from app.schemas.dataset import (
    DatasetCreate, DatasetDetail, DatasetImportRequest, DatasetSummary, DatasetValidateRequest,
    IndicatorValueRead,
)
from app.services.dataset_service import DatasetService
from app.services.errors import PayloadTooLargeError, ValidationFailedError
from app.services.ingest.filenames import original_filename
from app.services.ingest.types import IssueCode
from app.services.ingest.upload_service import UploadService

router = APIRouter(tags=["Наборы данных"], responses=error_responses(401))


def _read_upload(file: UploadFile, max_bytes: int) -> tuple[str, bytes]:
    filename = original_filename(file.filename)
    content = file.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise PayloadTooLargeError(
            f"Размер файла превышает допустимые {max_bytes // (1024 * 1024)} МБ",
            code=IssueCode.TOO_LARGE,
        )
    if not content:
        raise ValidationFailedError("Файл пуст", code=IssueCode.EMPTY_FILE)
    return filename, content


@router.get("/datasets/template", summary="Шаблон файла загрузки CSV или XLSX",
            responses=error_responses(401, 422))
def download_template(access: Access, db: DbSession, settings: AppSettings,
                      format: Annotated[Literal["csv", "xlsx"], Query()] = "csv"):
    payload, filename, media = UploadService(db, settings).template(access, format)
    return Response(content=payload, media_type=media,
                    headers={"Content-Disposition": f'attachment; filename="{filename}"',
                             "Cache-Control": "no-store"})


@router.post("/datasets/preview", summary="Предварительный просмотр загруженного файла",
             description="Проверяет формат и размер, определяет столбцы и типы, возвращает первые строки. "
                         "Файл сохраняется во временный каталог сервера и не попадает в PostgreSQL, "
                         "пока не будет выполнен импорт.",
             responses=error_responses(401, 413, 422))
def preview_dataset(access: Access, db: DbSession, settings: AppSettings,
                    file: Annotated[UploadFile, File(description="CSV или XLSX")]):
    filename, content = _read_upload(file, settings.upload_max_bytes)
    return UploadService(db, settings).preview(access, filename, content)


@router.post("/datasets/preview/validate", summary="Проверка качества данных загруженного файла",
             description="Укажите столбец периода и столбцы показателей. Ошибки (дубликаты, некорректные числа "
                         "и периоды) блокируют последующее сохранение.",
             responses=error_responses(401, 404, 422))
def validate_preview(data: DatasetValidateRequest, access: Access, db: DbSession, settings: AppSettings):
    return UploadService(db, settings).validate(
        access, data.staging_id, data.period_column, data.indicator_columns,
        data.category_column, data.granularity,
    )


@router.post("/organizations/{organization_id}/datasets/import", response_model=DatasetDetail,
             status_code=status.HTTP_201_CREATED, summary="Сохранение проверенного файла как набора данных",
             responses=error_responses(403, 404, 409, 422))
def import_dataset(organization_id: int, data: DatasetImportRequest, access: Access,
                   db: DbSession, settings: AppSettings):
    return UploadService(db, settings).import_file(access, organization_id, data)


@router.post("/organizations/{organization_id}/datasets/demo", response_model=DatasetDetail,
             status_code=status.HTTP_201_CREATED,
             summary="Загрузить демонстрационный набор в выбранную организацию",
             responses=error_responses(403, 404, 409, 422))
def import_demo_dataset(organization_id: int, access: Access, db: DbSession, settings: AppSettings):
    return UploadService(db, settings).import_demo(access, organization_id)


@router.get("/datasets/demo", summary="Описание демонстрационного набора")
def demo_dataset_info(access: Access):
    return {
        "name": "Демонстрационный набор",
        "synthetic": True,
        "periods": 36,
        "granularity": "month",
        "indicators": [
            "revenue", "sales_volume", "profit", "receivables", "payables",
            "inventory", "cash", "cf_operating", "cf_investing", "cf_financing",
        ],
        "note": "Условные ряды на 36 месяцев для проверки загрузки и расчёта.",
    }


@router.post("/organizations/{organization_id}/datasets", response_model=DatasetDetail,
             status_code=status.HTTP_201_CREATED, summary="Создание набора данных",
             description="Значения передаются в «длинном» формате: показатель × период × категория. "
                         "Для файлов CSV и XLSX используйте /datasets/preview и /datasets/import.",
             responses=error_responses(403, 404, 409, 422))
def create_dataset(organization_id: int, data: DatasetCreate, access: Access, db: DbSession):
    return DatasetService(db).create(access, organization_id, data)


@router.get("/datasets", response_model=Page[DatasetSummary], summary="Список доступных наборов данных",
            responses=error_responses(404))
def list_datasets(access: Access, db: DbSession, page: Pagination,
                  organization_id: Annotated[int | None, Query(description="Фильтр по организации")] = None):
    return DatasetService(db).search(access, organization_id, page.limit, page.offset)


@router.get("/organizations/{organization_id}/datasets", response_model=Page[DatasetSummary],
            summary="Наборы данных организации", responses=error_responses(404))
def list_organization_datasets(organization_id: int, access: Access, db: DbSession, page: Pagination):
    return DatasetService(db).search(access, organization_id, page.limit, page.offset)


@router.get("/datasets/{dataset_id}", response_model=DatasetDetail,
            summary="Набор данных: показатели, периоды, предупреждения", responses=error_responses(404))
def get_dataset(dataset_id: int, access: Access, db: DbSession):
    return DatasetService(db).detail(access, dataset_id)


@router.get("/datasets/{dataset_id}/schema", summary="Схема сохранённого набора данных",
            responses=error_responses(404))
def get_dataset_schema(dataset_id: int, access: Access, db: DbSession, settings: AppSettings):
    return UploadService(db, settings).schema(access, dataset_id)


@router.get("/datasets/{dataset_id}/quality", summary="Сводка качества сохранённого набора",
            responses=error_responses(404))
def get_dataset_quality(dataset_id: int, access: Access, db: DbSession, settings: AppSettings):
    return UploadService(db, settings).quality(access, dataset_id)


@router.get("/datasets/{dataset_id}/values", response_model=Page[IndicatorValueRead],
            summary="Значения показателей набора", responses=error_responses(404, 422))
def get_dataset_values(
    dataset_id: int, access: Access, db: DbSession,
    indicators: Annotated[list[str] | None, Query(description="Коды показателей")] = None,
    period_from: Annotated[date | None, Query(alias="from")] = None,
    period_to: Annotated[date | None, Query(alias="to")] = None,
    limit: Annotated[int, Query(ge=1, le=10_000)] = 1000,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return DatasetService(db).values(access, dataset_id, indicators, period_from, period_to, limit, offset)


@router.delete("/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Удаление набора данных и его исследований", responses=error_responses(403, 404))
def delete_dataset(dataset_id: int, access: Access, db: DbSession):
    DatasetService(db).delete(access, dataset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
