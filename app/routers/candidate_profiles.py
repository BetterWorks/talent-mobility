from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.candidate_profile import CandidateProfile, CandidateProfileDAO, CandidateProfileStatus
from app.routers.user_directory import get_user_details


router = APIRouter(prefix="/api/candidate-profiles", tags=["candidate-profiles"])


def _enrich(profile: CandidateProfile) -> dict:
    """Fold the stubbed user identity + HRIS blocks onto a candidate profile,
    joined on user_uuid. Also overwrites the identity fields inside
    profile_data (name/role/department/location/tenure/manager), which the
    pipeline left as UUID/empty because HRIS was unavailable at match time, so
    the UI shows real names wherever it reads them. `profile`/`hris` are None
    for users not in the stub."""
    data = profile.model_dump(mode="json")
    details = get_user_details(profile.user_uuid)
    data["profile"] = details["profile"] if details else None
    data["hris"] = details["hris"] if details else None

    if details:
        prof = details["profile"]
        pd = data.get("profile_data") or {}
        pd["name"] = prof["name"]
        pd["current_role"] = prof["role"]
        pd["department"] = prof["department"]
        pd["location"] = prof["location"]
        pd["tenure"] = prof["tenure"]
        pd["current_manager"] = prof["current_manager"]
        data["profile_data"] = pd
    return data


@router.get("/by-run/{run_id}")
async def list_candidate_profiles_by_run(
    run_id: UUID,
    cost_impact: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_desc: bool = True,
    session: AsyncSession = Depends(get_session),
):
    dao = CandidateProfileDAO(session)
    profiles = await dao.list_by_run(run_id, cost_impact=cost_impact, sort_by=sort_by, sort_desc=sort_desc)
    return [_enrich(p) for p in profiles]


@router.get("/{profile_id}")
async def get_candidate_profile(
    profile_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    dao = CandidateProfileDAO(session)
    profile = await dao.get_by_id(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
    return _enrich(profile)


@router.patch("/{profile_id}/status", response_model=CandidateProfile)
async def update_candidate_profile_status(
    profile_id: UUID,
    status: CandidateProfileStatus,
    session: AsyncSession = Depends(get_session),
):
    dao = CandidateProfileDAO(session)
    profile = await dao.update(profile_id, status=status.value)
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
    return profile
