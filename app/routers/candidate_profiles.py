from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.candidate_profile import CandidateProfile, CandidateProfileDAO, CandidateProfileStatus


router = APIRouter(prefix="/api/candidate-profiles", tags=["candidate-profiles"])


@router.get("/by-run/{run_id}", response_model=list[CandidateProfile])
async def list_candidate_profiles_by_run(
    run_id: UUID,
    cost_impact: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_desc: bool = True,
    session: AsyncSession = Depends(get_session),
):
    dao = CandidateProfileDAO(session)
    return await dao.list_by_run(run_id, cost_impact=cost_impact, sort_by=sort_by, sort_desc=sort_desc)


@router.get("/{profile_id}", response_model=CandidateProfile)
async def get_candidate_profile(
    profile_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    dao = CandidateProfileDAO(session)
    profile = await dao.get_by_id(profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate profile not found")
    return profile


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
