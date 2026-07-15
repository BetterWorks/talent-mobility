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


class Confidence(str, Enum):
    LOW = 'Low'
    MEDIUM = 'Medium'
    HIGH = 'High'


class ReadinessFactor(BaseModel):
    label: str
    level: ReadinessLevel


class LLMCandidateInsights(BaseModel):
    """The subset of a candidate profile synthesized by the LLM from a user's
    retrieved evidence. This is the strict parse target for the synthesis call.

    Deliberately excludes retrieval-owned fields (match_score), HRIS facts
    (name, role, department, location, tenure, manager, savings) and the cost
    figure, all of which are injected by the service. The LLM only produces
    evidence-grounded qualitative content.
    """
    summary: Optional[str] = None
    strengths: List[str] = []
    gaps: List[str] = []
    career_signals: List[str] = []
    evidence: List[str] = []
    readiness_factors: List[ReadinessFactor] = []
    confidence: Confidence = Confidence.MEDIUM
    ready_in: str  # LLM estimate, e.g. "4-6 weeks"
    cost_impact: CostImpact = CostImpact.MEDIUM


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

    match_score: int  # from retrieval, not the LLM
    ready_in: str
    cost_impact: CostImpact
    estimated_savings: Optional[str] = None  # max_salary - current_salary, from HRIS
    confidence: Confidence = Confidence.MEDIUM

    summary: Optional[str] = None
    strengths: List[str] = []
    gaps: List[str] = []
    career_signals: List[str] = []
    evidence: List[str] = []
    readiness_factors: List[ReadinessFactor] = []
