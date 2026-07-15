from datetime import date, datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Column, Field, SQLModel

from app.db import meta
from app.utils.common import get_utc_now


class EvidenceRequestStatus(str, Enum):
    PENDING = 'pending'
    RECEIVED = 'received'
    DISPUTED = 'disputed'


class EvidenceRequestBase(SQLModel):
    id: UUID = Field(default_factory=uuid4, nullable=False, primary_key=True)
    created: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))
    modified: Optional[datetime] = Field(default_factory=get_utc_now, sa_column=Column(DateTime(timezone=True)))

    candidate_match_id: UUID = Field()
    evidence_type: str = Field()

    # From Haven's org-wide user search (BWUserIdentityAutoComplete) — a different identity
    # source than the local candidate/user_directory stub, so we only have the id, not a name.
    assignee_id: UUID = Field()

    due_date: Optional[date] = Field(default=None)
    status: str = Field(default=EvidenceRequestStatus.PENDING.value)
    response: Optional[str] = Field(default=None)
    note: Optional[str] = Field(default=None)


class EvidenceRequest(EvidenceRequestBase, table=True):
    __tablename__ = 'evidence_request'
    metadata = meta

    class Config:
        arbitrary_types_allowed = True


class EvidenceRequestDAO:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, data: EvidenceRequestBase) -> EvidenceRequest:
        new_request = EvidenceRequest(**data.model_dump())
        self.session.add(new_request)
        await self.session.commit()
        await self.session.refresh(new_request)
        return new_request

    async def get_by_id(self, evidence_request_id: UUID) -> Optional[EvidenceRequest]:
        result = await self.session.execute(
            select(EvidenceRequest).where(EvidenceRequest.id == evidence_request_id)
        )
        return result.scalars().first()

    async def list_by_candidate(self, candidate_match_id: UUID) -> List[EvidenceRequest]:
        result = await self.session.execute(
            select(EvidenceRequest).where(
                EvidenceRequest.candidate_match_id == candidate_match_id
            ).order_by(EvidenceRequest.created.desc())
        )
        return result.scalars().all()

    async def update(self, evidence_request_id: UUID, **kwargs) -> Optional[EvidenceRequest]:
        kwargs['modified'] = kwargs.get('modified') or get_utc_now(tz=False)
        statement = (
            update(EvidenceRequest).
            returning(EvidenceRequest).
            where(EvidenceRequest.id == evidence_request_id).
            values(**kwargs)
        )
        result = await self.session.execute(statement=statement)
        await self.session.commit()
        return result.scalars().first()
