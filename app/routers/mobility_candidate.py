from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.candidate_profile import CandidateProfile, CandidateProfileDAO, CandidateProfileStatus
from app.db.internal_mobility_request import InternalMobilityRequestDAO
from app.db.run_ai_matches import RunAiMatchesDAO
from app.services.candidate_mapping import serialize_candidate_attributes
from app.utils.exceptions import MobilityApiError


# Router for the Candidate Deep Dive & AI Insights screen. Reuses the read
# logic from GET /api/candidate-profiles/{profile_id}, resolved under the
# path and JSON:API-shaped response the frontend expects.
router = APIRouter(prefix="/candidates", tags=["Candidate"])


async def _resolve_request_context(
    session: AsyncSession, profile: CandidateProfile
) -> tuple[Optional[UUID], Optional[Decimal]]:
    """Resolve the candidate's role request id and its max_salary (for
    cost_difference), via the run that produced this profile."""
    if not profile.run_ai_match:
        return None, None
    run = await RunAiMatchesDAO(session).get_by_id(profile.run_ai_match)
    role_request_id = run.request_id if run else None
    if not role_request_id:
        return None, None
    request = await InternalMobilityRequestDAO(session).get_by_id(role_request_id)
    return role_request_id, (request.max_salary if request else None)


def _candidate_response(
    profile: CandidateProfile, role_request_id: Optional[UUID], max_salary: Optional[Decimal]
) -> dict[str, Any]:
    return {
        "data": {
            "type": "mobility_candidate",
            "id": str(profile.id),
            "attributes": serialize_candidate_attributes(profile, role_request_id, max_salary),
        },
        "included": [],
    }


@router.get("/{cm_id}")
async def get_candidate(cm_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    candidate_dao = CandidateProfileDAO(session)
    profile = await candidate_dao.get_by_id(cm_id)
    if not profile:
        raise MobilityApiError(404, "Candidate not found")

    role_request_id, max_salary = await _resolve_request_context(session, profile)
    return _candidate_response(profile, role_request_id, max_salary)


@router.post("/{cm_id}/move-to-decision")
async def move_candidate_to_decision(cm_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Move candidate to Decision (status -> decision). Real evidence-snapshot
    freezing isn't built yet (no Evidence/Decision tables) — this only flips
    status for now, which is all the Candidate Deep Dive screen needs to
    proceed to the Decision Review stage."""
    candidate_dao = CandidateProfileDAO(session)
    profile = await candidate_dao.update(cm_id, status=CandidateProfileStatus.DECISION.value)
    if not profile:
        raise MobilityApiError(404, "Candidate not found")

    role_request_id, max_salary = await _resolve_request_context(session, profile)
    return _candidate_response(profile, role_request_id, max_salary)
