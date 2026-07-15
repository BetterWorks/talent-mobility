from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.candidate_profile import CandidateProfile, CandidateProfileDAO, CandidateProfileStatus


router = APIRouter(prefix="/api/candidate-profiles", tags=["candidate-profiles"])


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
