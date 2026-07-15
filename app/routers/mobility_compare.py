from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.candidate_profile import CandidateProfileDAO
from app.db.internal_mobility_request import InternalMobilityRequestDAO
from app.services.candidate_mapping import serialize_candidate_attributes


# Router for the Compare Candidates screen. Reuses the same per-candidate
# read logic as GET /candidates/{cmId} (mobility_candidate.py) for each
# requested candidate_match_id, reshaped into the side-by-side Compare
# contract instead of doing a separate DB query.
router = APIRouter(prefix="/role-requests", tags=["Compare"])


def _compare_candidate(cm_id: UUID, attributes: dict[str, Any], currency: str) -> dict[str, Any]:
    readiness = {f["label"]: f["value"] for f in attributes.get("readiness_factors") or []}
    cost_difference = attributes.get("cost_difference")
    return {
        "candidate_match_id": str(cm_id),
        "name": (attributes.get("employee") or {}).get("name"),
        "match_pct": attributes.get("match_pct"),
        "ready_in_label": attributes.get("ready_in_label"),
        "current_role": attributes.get("current_role"),
        "cost_impact": attributes.get("cost_impact"),
        # Labels are fixed by the synthesis prompt (see app/prompt/candidate_profile.py) —
        # "Skill Match" / "Performance" / "Learning Agility" always present.
        "skill_match": readiness.get("Skill Match"),
        "performance": readiness.get("Performance"),
        "learning_agility": readiness.get("Learning Agility"),
        "key_strengths": attributes.get("strengths") or [],
        "top_gaps": attributes.get("top_gaps") or [],
        "est_cost": {"currency": currency, "amount": cost_difference} if cost_difference is not None else None,
    }


@router.get("/{request_id}/candidates/compare")
async def compare_candidates(
    request_id: UUID,
    candidate_match_id: list[UUID] = Query(default=[], alias="filter[candidate_match_id][]"),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Side-by-side comparison for up to 3 candidates, identical criteria.
    Candidate ids that don't resolve to a profile are silently dropped rather
    than failing the whole comparison."""
    role_request = await InternalMobilityRequestDAO(session).get_by_id(request_id)
    max_salary: Optional[Any] = role_request.max_salary if role_request else None
    currency = (role_request.budget_currency if role_request else None) or "USD"

    candidate_dao = CandidateProfileDAO(session)
    candidates: list[dict[str, Any]] = []
    for cm_id in candidate_match_id:
        profile = await candidate_dao.get_by_id(cm_id)
        if not profile:
            continue
        attributes = serialize_candidate_attributes(profile, request_id, max_salary)
        candidates.append(_compare_candidate(profile.id, attributes, currency))

    return {
        "data": {
            "type": "mobility_compare",
            "id": str(request_id),
            "attributes": {"candidates": candidates},
        },
    }
