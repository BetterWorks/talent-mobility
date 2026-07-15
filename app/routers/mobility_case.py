from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.case import Case, CaseDAO
from app.utils.exceptions import MobilityApiError


# Case lookup by id — shared across all case-scoped stages (Consent/Planning/Tracking/
# Outcomes). Nothing else fetches a bare case resource: it's normally only known via the
# case_id a stage action returns, so the frontend's stage stepper needs this to resolve
# role_request_id/candidate_match_id when a case-scoped screen is entered directly
# (deep link / reload) rather than navigated to from Decision.
router = APIRouter(prefix="/cases", tags=["Case"])


def _serialize(case: Case) -> dict[str, Any]:
    return {
        "data": {
            "type": "mobility_case",
            "id": str(case.id),
            "attributes": {
                "role_request_id": str(case.role_request_id),
                "candidate_match_id": str(case.candidate_match_id),
                "decision_id": str(case.decision_id) if case.decision_id else None,
                "status": case.status,
            },
        },
    }


@router.get("/{case_id}")
async def get_case(case_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    case = await CaseDAO(session).get_by_id(case_id)
    if not case:
        raise MobilityApiError(404, "Case not found")
    return _serialize(case)
