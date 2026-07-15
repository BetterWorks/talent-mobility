from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class MatchRunStatus(str, Enum):
    """External status the UI polls on — maps from our internal
    RunAiMatchesStatus (pending/running/completed/failed)."""
    EMPTY = 'empty'
    RUNNING = 'running'
    READY = 'ready'
    FAILED = 'failed'


class ResourceMeta(BaseModel):
    created_on: Optional[datetime] = None
    modified_on: Optional[datetime] = None


class MatchRunAttributes(BaseModel):
    role_request_id: UUID
    status: MatchRunStatus
    model_version: Optional[str] = None
    prompt_version: Optional[str] = None
    policy_version: Optional[str] = None
    eligible_count: Optional[int] = None
    excluded_count: Optional[int] = None
    completed_at: Optional[datetime] = None


class MatchRunResource(BaseModel):
    type: str = 'mobility_match_run'
    id: UUID
    meta: ResourceMeta
    attributes: MatchRunAttributes


class MatchRunDetailResponse(BaseModel):
    """JSON:API detail envelope for GET .../match-runs/latest.

    Matches openapi.yaml's MatchRunDetailResponse. The UI sends only the
    role_request id in the path (polling GET, no body) and expects this
    shape back, polling `data.attributes.status` for running -> ready|failed.
    """
    data: MatchRunResource
