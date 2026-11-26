from typing import Annotated

from fastapi import APIRouter, File, Response, UploadFile

from app.api.deps import Access, DbSession, error_responses
from app.schemas.governance import (
    AlertRead, FindingRead, MeasureCreate, MeasureEventRead, MeasureRead, MeasureUpdate,
    RecommendationConvert, RecommendationRead, RecommendationUpdate, ScenarioCreate, ScenarioRead,
    TargetUpsert, ThresholdUpsert,
)
from app.services.governance_service import GovernanceService

router = APIRouter(tags=["Антикризисное управление"], responses=error_responses(401))
WRITE = error_responses(403, 404, 422)


@router.get("/organizations/{organization_id}/findings", response_model=list[FindingRead])
def list_findings(organization_id: int, access: Access, db: DbSession, run_id: int | None = None):
    return GovernanceService(db).list_findings(access, organization_id, run_id)


@router.get("/organizations/{organization_id}/alerts", response_model=list[AlertRead])
def list_alerts(organization_id: int, access: Access, db: DbSession, run_id: int | None = None):
    return GovernanceService(db).list_alerts(access, organization_id, run_id)


@router.get("/organizations/{organization_id}/recommendations", response_model=list[RecommendationRead])
def list_recommendations(organization_id: int, access: Access, db: DbSession, run_id: int | None = None):
    return GovernanceService(db).list_recommendations(access, organization_id, run_id)


@router.patch("/recommendations/{recommendation_id}", response_model=RecommendationRead, responses=WRITE)
def update_recommendation(recommendation_id: int, body: RecommendationUpdate, access: Access, db: DbSession):
    return GovernanceService(db).update_recommendation(access, recommendation_id, body.status, body.comment)


@router.post("/recommendations/{recommendation_id}/convert", response_model=MeasureRead, responses=WRITE)
def convert_recommendation(recommendation_id: int, body: RecommendationConvert, access: Access, db: DbSession):
    return GovernanceService(db).convert_recommendation(access, recommendation_id, body.due_at, body.assignee_id)


@router.get("/organizations/{organization_id}/measures", response_model=list[MeasureRead])
def list_measures(organization_id: int, access: Access, db: DbSession):
    return GovernanceService(db).list_measures(access, organization_id)


@router.post("/organizations/{organization_id}/measures", response_model=MeasureRead, responses=WRITE)
def create_measure(organization_id: int, body: MeasureCreate, access: Access, db: DbSession):
    return GovernanceService(db).create_measure(access, organization_id, body.model_dump())


@router.patch("/measures/{measure_id}", response_model=MeasureRead, responses=WRITE)
def update_measure(measure_id: int, body: MeasureUpdate, access: Access, db: DbSession):
    return GovernanceService(db).update_measure(access, measure_id, body.model_dump(exclude_unset=True))


@router.delete("/measures/{measure_id}", status_code=204, responses=WRITE)
def delete_measure(measure_id: int, access: Access, db: DbSession):
    GovernanceService(db).delete_measure(access, measure_id)
    return Response(status_code=204)


@router.get("/measures/{measure_id}/events", response_model=list[MeasureEventRead])
def measure_events(measure_id: int, access: Access, db: DbSession):
    return GovernanceService(db).measure_events(access, measure_id)


@router.get("/organizations/{organization_id}/profile")
def org_profile(organization_id: int, access: Access, db: DbSession):
    targets, thresholds = GovernanceService(db).list_targets(access, organization_id)
    return {"targets": targets, "thresholds": thresholds}


@router.post("/organizations/{organization_id}/targets", responses=WRITE)
def upsert_target(organization_id: int, body: TargetUpsert, access: Access, db: DbSession):
    return GovernanceService(db).upsert_target(access, organization_id, body.model_dump())


@router.post("/organizations/{organization_id}/thresholds", responses=WRITE)
def upsert_threshold(organization_id: int, body: ThresholdUpsert, access: Access, db: DbSession):
    return GovernanceService(db).upsert_threshold(access, organization_id, body.model_dump())


@router.post("/organizations/{organization_id}/profile/import", responses=WRITE)
def import_profile(
    organization_id: int,
    access: Access,
    db: DbSession,
    file: Annotated[UploadFile, File(description="CSV или XLSX с планами и границами")],
):
    content = file.file.read()
    return GovernanceService(db).import_profile_file(
        access, organization_id, file.filename or "norms.xlsx", content,
    )


@router.get("/organizations/{organization_id}/scenarios", response_model=list[ScenarioRead])
def list_scenarios(organization_id: int, access: Access, db: DbSession):
    return GovernanceService(db).list_scenarios(access, organization_id)


@router.post("/organizations/{organization_id}/scenarios", response_model=ScenarioRead, responses=WRITE)
def create_scenario(organization_id: int, body: ScenarioCreate, access: Access, db: DbSession):
    return GovernanceService(db).create_scenario(access, organization_id, body.model_dump())


@router.get("/analyses/{run_id}/compare")
def compare_runs(run_id: int, other_id: int, access: Access, db: DbSession):
    return GovernanceService(db).compare_runs(access, run_id, other_id)


@router.get("/organizations/{organization_id}/audit")
def org_audit(organization_id: int, access: Access, db: DbSession):
    return GovernanceService(db).audit_feed(access, organization_id)
