from fastapi import APIRouter, Response, status

from app.api.deps import Access, DbSession, Pagination, error_responses
from app.models.enums import OrganizationAccessLevel
from app.schemas.admin import OrganizationMemberRead
from app.schemas.common import Page
from app.schemas.organization import (
    OrganizationCreate, OrganizationEmployeeCreate, OrganizationMemberAssign, OrganizationRead,
    OrganizationSummary, OrganizationUpdate,
)
from app.services.organization_service import OrganizationService

router = APIRouter(prefix="/organizations", tags=["Организации"], responses=error_responses(401))


@router.get("", response_model=Page[OrganizationSummary], summary="Список организаций пользователя")
def list_organizations(access: Access, db: DbSession, page: Pagination):
    return OrganizationService(db).search(access, page.limit, page.offset)


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED,
             summary="Создание организации", responses=error_responses(409, 422))
def create_organization(data: OrganizationCreate, access: Access, db: DbSession):
    service = OrganizationService(db)
    created = service.create(access, data)
    return service.to_read(access, created)


@router.get("/{organization_id}", response_model=OrganizationSummary, summary="Карточка организации",
            responses=error_responses(404))
def get_organization(organization_id: int, access: Access, db: DbSession):
    return OrganizationService(db).summary(access, organization_id)


@router.patch("/{organization_id}", response_model=OrganizationRead, summary="Изменение организации",
              responses=error_responses(403, 404, 409, 422))
def update_organization(organization_id: int, data: OrganizationUpdate, access: Access, db: DbSession):
    service = OrganizationService(db)
    updated = service.update(access, organization_id, data)
    return service.to_read(access, updated)


@router.delete("/{organization_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Удаление организации вместе с наборами данных и исследованиями",
               responses=error_responses(403, 404))
def delete_organization(organization_id: int, access: Access, db: DbSession):
    OrganizationService(db).delete(access, organization_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{organization_id}/members", response_model=list[OrganizationMemberRead],
            summary="Сотрудники организации", responses=error_responses(403, 404))
def list_members(organization_id: int, access: Access, db: DbSession):
    return OrganizationService(db).member_reads(access, organization_id)


@router.post("/{organization_id}/members", response_model=OrganizationMemberRead,
            summary="Назначить существующего пользователя сотрудником",
            responses=error_responses(403, 404, 422))
def assign_member(organization_id: int, data: OrganizationMemberAssign, access: Access, db: DbSession):
    return OrganizationService(db).assign_member(
        access, organization_id, data.user_id, data.login, OrganizationAccessLevel(data.access_level),
    )


@router.put("/{organization_id}/members/{user_id}", response_model=OrganizationMemberRead,
            summary="Изменить уровень доступа сотрудника",
            responses=error_responses(403, 404, 422))
def update_member(organization_id: int, user_id: int, data: OrganizationMemberAssign,
                  access: Access, db: DbSession):
    return OrganizationService(db).assign_member(
        access, organization_id, user_id, None, OrganizationAccessLevel(data.access_level),
    )


@router.post("/{organization_id}/employees", response_model=OrganizationMemberRead,
             status_code=status.HTTP_201_CREATED,
             summary="Создать учётную запись аналитика и назначить в организацию",
             responses=error_responses(403, 404, 409, 422))
def create_employee(organization_id: int, data: OrganizationEmployeeCreate, access: Access, db: DbSession):
    return OrganizationService(db).create_employee(access, organization_id, data)


@router.delete("/{organization_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Отозвать доступ сотрудника", responses=error_responses(403, 404, 422))
def revoke_member(organization_id: int, user_id: int, access: Access, db: DbSession):
    OrganizationService(db).revoke_access(access, organization_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{organization_id}/workspace/clear", summary="Очистить наборы и исследования организации",
             responses=error_responses(403, 404))
def clear_workspace(organization_id: int, access: Access, db: DbSession):
    return OrganizationService(db).clear_workspace(access, organization_id)
