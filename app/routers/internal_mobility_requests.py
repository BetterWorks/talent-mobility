from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.internal_mobility_request import (
    InternalMobilityRequest, InternalMobilityRequestBase, InternalMobilityRequestDAO
)


router = APIRouter(prefix="/api/internal-mobility-requests", tags=["internal-mobility-requests"])


@router.post("/", response_model=InternalMobilityRequest)
async def create_internal_mobility_request(
    data: InternalMobilityRequestBase,
    session: AsyncSession = Depends(get_session),
):
    dao = InternalMobilityRequestDAO(session)
    return await dao.create(data)


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


@router.get("/", response_model=list[InternalMobilityRequest])
async def list_internal_mobility_requests(
    business_unit: str | None = None,
    hiring_manager: str | None = None,
    seniority_level: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    dao = InternalMobilityRequestDAO(session)
    return await dao.list(
        business_unit=business_unit,
        hiring_manager=hiring_manager,
        seniority_level=seniority_level,
    )
