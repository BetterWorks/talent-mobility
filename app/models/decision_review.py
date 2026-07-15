from datetime import date
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class DecisionWriteAttributes(BaseModel):
    outcome: str
    reason_code: Optional[str] = None
    note: Optional[str] = None
    review_date: Optional[date] = None


class DecisionCreateRequest(BaseModel):
    """POST /candidates/{cmId}/decision body — matches openapi.yaml's
    DecisionCreateRequest (JSON:API write envelope: data.attributes)."""

    class Data(BaseModel):
        type: Optional[str] = None
        attributes: DecisionWriteAttributes

    data: Data


class EvidenceCreateAttributes(BaseModel):
    evidence_type: str
    assignee_id: UUID
    due_date: date
    note: Optional[str] = None


class EvidenceCreateRequest(BaseModel):
    """POST /candidates/{cmId}/evidence-requests body."""

    class Data(BaseModel):
        type: Optional[str] = None
        attributes: EvidenceCreateAttributes

    data: Data


class EvidencePatchAttributes(BaseModel):
    status: Optional[str] = None
    response: Optional[str] = None


class EvidencePatchRequest(BaseModel):
    """PATCH /evidence-requests/{evId} body."""

    class Data(BaseModel):
        type: Optional[str] = None
        attributes: EvidencePatchAttributes

    data: Data
