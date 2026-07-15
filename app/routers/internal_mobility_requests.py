from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.candidate_profile import CandidateProfileDAO
from app.db.internal_mobility_request import (
    InternalMobilityRequest, InternalMobilityRequestBase, InternalMobilityRequestDAO, InternalMobilityRequestStatus
)
from app.db.run_ai_matches import RunAiMatchesDAO
from app.models.role_request import RoleRequestCreatePlainRequest
from app.utils.common import get_utc_now


router = APIRouter(prefix="/role-requests", tags=["RoleRequest"])


@router.post("/", response_model=InternalMobilityRequest)
async def create_internal_mobility_request(
    payload: RoleRequestCreatePlainRequest,
    session: AsyncSession = Depends(get_session),
):
    dao = InternalMobilityRequestDAO(session)
    return await dao.create(InternalMobilityRequestBase(**payload.model_dump()))


@router.get("/{request_id}", response_model=InternalMobilityRequest)
async def get_internal_mobility_request(
    request_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    dao = InternalMobilityRequestDAO(session)
    request = await dao.get_by_id(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    return request


@router.get("/")
async def list_internal_mobility_requests(
    business_unit: str | None = None,
    hiring_manager: str | None = None,
    seniority_level: str | None = None,
    status: str | None = None,
    page_limit: int = 20,
    page_offset: int = 0,
    session: AsyncSession = Depends(get_session),
):
    """Dashboard screen: recent-mobility-requests table (JSON:API list
    envelope) plus KPI tiles in `meta.kpis`."""
    request_dao = InternalMobilityRequestDAO(session)
    run_dao = RunAiMatchesDAO(session)
    candidate_dao = CandidateProfileDAO(session)

    requests = await request_dao.list(
        business_unit=business_unit,
        hiring_manager=hiring_manager,
        seniority_level=seniority_level,
        status=status,
    )

    total = len(requests)
    page = requests[page_offset:page_offset + page_limit]

    at_risk_fill_ratio = 0.8
    finalized_statuses = {InternalMobilityRequestStatus.APPROVED.value, InternalMobilityRequestStatus.CLOSED.value}
    now = get_utc_now()

    data = []
    kpis = {"open_requests": 0, "in_progress": 0, "approved": 0, "at_risk_roles": 0}
    for request in requests:
        if request.status == InternalMobilityRequestStatus.OPEN.value:
            kpis["open_requests"] += 1
        elif request.status == InternalMobilityRequestStatus.IN_PROGRESS.value:
            kpis["in_progress"] += 1
        elif request.status == InternalMobilityRequestStatus.APPROVED.value:
            kpis["approved"] += 1

        if request.status not in finalized_statuses and request.hiring_estimate_in_days and request.created:
            elapsed_days = (now - request.created).total_seconds() / 86400
            if elapsed_days >= at_risk_fill_ratio * request.hiring_estimate_in_days:
                kpis["at_risk_roles"] += 1

    for request in page:
        latest_run = await run_dao.get_latest_by_request(request.id)
        candidate_count = 0
        if latest_run:
            candidate_count = len(await candidate_dao.get_by_run(latest_run.id))

        data.append({
            "type": "mobility_role_request",
            "id": str(request.id),
            "meta": {
                "created_on": request.created,
                "modified_on": request.modified,
            },
            "attributes": {
                "role_title": request.title,
                "hiring_manager": request.hiring_manager,
                "candidate_count": candidate_count,
                "status": request.status,
                "estimated_savings_amount": float(request.external_hiring_cost or 0),
                "budget_currency": request.budget_currency,
            },
        })

    return {
        "data": data,
        "included": [],
        "meta": {
            "page": {"limit": page_limit, "offset": page_offset, "total": total},
            "kpis": kpis,
        },
    }


@router.patch("/{request_id}/status", response_model=InternalMobilityRequest)
async def update_internal_mobility_request_status(
    request_id: UUID,
    status: InternalMobilityRequestStatus,
    session: AsyncSession = Depends(get_session),
):
    dao = InternalMobilityRequestDAO(session)
    request = await dao.update(request_id, status=status.value)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    return request


@router.get("/{request_id}/benchmarks")
async def get_role_request_benchmarks(
    request_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Role & AI Shortlist screen: header benchmark tiles (Est. External Hire
    Cost, Est. Time to Fill, Internal Readiness, Est. Savings). Time-to-fill,
    internal-readiness and savings-pct are static placeholders — not yet
    computed from real data."""
    dao = InternalMobilityRequestDAO(session)
    request = await dao.get_by_id(request_id)
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    external_hire_cost = float(request.external_hiring_cost or 0)
    estimated_savings = round(external_hire_cost * 0.67, 2)

    return {
        "external_hire_cost": external_hire_cost,
        "time_to_fill_days": request.hiring_estimate_in_days or 90,
        "internal_readiness_count": 47,
        "estimated_savings": {
            "amount": estimated_savings,
            "pct": 67,
        },
    }
