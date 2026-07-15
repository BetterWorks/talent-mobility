from enum import Enum
from typing import List, Optional

from pydantic import BaseModel


class ReadinessLevel(str, Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'


class CostImpact(str, Enum):
    LOW = 'Low'
    MEDIUM = 'Medium'
    HIGH = 'High'


class ReadinessFactor(BaseModel):
    label: str
    level: ReadinessLevel


class CandidateProfileData(BaseModel):
    """Fixed shape stored in candidate_profile.profile_data (JSONB).

    Mirrors the fields the AI Shortlist / Candidate Deep Dive screens render
    from the prototype's mock candidate objects (see `C.arjun` etc. in
    Mobility_Match_Prototype.html).
    """
    name: str
    current_role: str
    department: Optional[str] = None
    location: Optional[str] = None
    tenure: Optional[str] = None
    current_manager: Optional[str] = None

    match_score: int
    ready_in: str
    cost_impact: CostImpact
    estimated_savings: Optional[str] = None

    summary: Optional[str] = None
    strengths: List[str] = []
    gaps: List[str] = []
    career_signals: List[str] = []
    evidence: List[str] = []
    readiness_factors: List[ReadinessFactor] = []
