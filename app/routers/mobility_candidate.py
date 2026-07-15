from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.candidate_profile import CandidateProfileDAO
from app.db.run_ai_matches import RunAiMatchesDAO
from app.services.candidate_mapping import serialize_candidate_attributes


# Router for the Candidate Deep Dive & AI Insights screen. Reuses the read
# logic from GET /api/candidate-profiles/{profile_id}, resolved under the
# path and JSON:API-shaped response the frontend expects.
router = APIRouter(prefix="/candidates", tags=["Candidate"])


@router.get("/{cm_id}")
async def get_candidate(cm_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    candidate_dao = CandidateProfileDAO(session)
    profile = await candidate_dao.get_by_id(cm_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate not found")

    role_request_id = None
    if profile.run_ai_match:
        run_dao = RunAiMatchesDAO(session)
        run = await run_dao.get_by_id(profile.run_ai_match)
        role_request_id = run.request_id if run else None

    return {
        "data": {
            "type": "mobility_candidate",
            "id": str(profile.id),
            "attributes": serialize_candidate_attributes(profile, role_request_id),
        },
        "included": [],
    }
