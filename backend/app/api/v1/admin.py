from typing import Annotated, Literal

from fastapi import APIRouter, Query, Response, status

from app.api.deps import Access, DbSession, Pagination, error_responses
from app.schemas.admin import (
    AdminOverview, AdminPasswordReset, AdminUserCreate, AdminUserRead, AdminUserUpdate, OrganizationMemberRead,
)
from app.schemas.common import Page
from app.services.admin_service import AdminService

router = APIRouter(prefix="/admin", tags=["Администрирование"], responses=error_responses(401, 403))


@router.get("/overview", response_model=AdminOverview, summary="Сводка по системе")
def overview(access: Access, db: DbSession):
    return AdminService(db).overview(access)


@router.get("/users", response_model=Page[AdminUserRead], summary="Список учётных записей")
def list_users(
    access: Access, db: DbSession, page: Pagination,
    q: Annotated[str | None, Query(max_length=100)] = None,
):
    return AdminService(db).list_users(access, q, page.limit, page.offset)


@router.post("/users", response_model=AdminUserRead, status_code=status.HTTP_201_CREATED,
             summary="Создание учётной записи", responses=error_responses(401, 403, 409, 422))
def create_user(data: AdminUserCreate, access: Access, db: DbSession):
    return AdminService(db).create_user(access, data)


@router.get("/users/{user_id}", response_model=AdminUserRead, summary="Учётная запись",
            responses=error_responses(401, 403, 404))
def get_user(user_id: int, access: Access, db: DbSession):
    return AdminService(db).get_user(access, user_id)


@router.patch("/users/{user_id}", response_model=AdminUserRead, summary="Изменение учётной записи",
              responses=error_responses(401, 403, 404, 422))
def update_user(user_id: int, data: AdminUserUpdate, access: Access, db: DbSession):
    return AdminService(db).update_user(access, user_id, data)


@router.post("/users/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT,
             summary="Сброс пароля администратором", responses=error_responses(401, 403, 404, 422))
def reset_password(user_id: int, data: AdminPasswordReset, access: Access, db: DbSession):
    AdminService(db).reset_password(access, user_id, data)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/unlock", response_model=AdminUserRead, summary="Снятие блокировки входа",
             responses=error_responses(401, 403, 404))
def unlock_user(user_id: int, access: Access, db: DbSession):
    return AdminService(db).unlock_user(access, user_id)


@router.get("/organizations/{organization_id}/members", response_model=list[OrganizationMemberRead],
            summary="Сотрудники с доступом к организации", responses=error_responses(401, 403, 404))
def list_members(organization_id: int, access: Access, db: DbSession):
    return AdminService(db).organization_members(access, organization_id)


@router.put("/organizations/{organization_id}/access/{user_id}", response_model=OrganizationMemberRead,
            summary="Предоставить доступ к организации", responses=error_responses(401, 403, 404, 409, 422))
def grant_access(
    organization_id: int, user_id: int, access: Access, db: DbSession,
    access_level: Annotated[Literal["view", "edit"], Query()] = "view",
):
    return AdminService(db).grant_organization_access(access, organization_id, user_id, access_level)


@router.delete("/organizations/{organization_id}/access/{user_id}", status_code=status.HTTP_204_NO_CONTENT,
               summary="Отозвать доступ к организации", responses=error_responses(401, 403, 404))
def revoke_access(organization_id: int, user_id: int, access: Access, db: DbSession):
    AdminService(db).revoke_organization_access(access, organization_id, user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
