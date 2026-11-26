from fastapi import APIRouter

from app.api.v1 import admin, analyses, auth, dashboard, datasets, governance, health, organizations, reference, reports

api_router = APIRouter(prefix="/api/v1")
for module in (health, auth, organizations, reference, datasets, analyses, dashboard, reports, admin, governance):
    api_router.include_router(module.router)
