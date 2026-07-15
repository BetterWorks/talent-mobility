import re
from typing import Any, Optional
from uuid import UUID

from app.db.candidate_profile import CandidateProfile, CandidateProfileStatus


# candidate_profile.status is an int (CandidateProfileStatus); the frontend's
# CandidateStatus is a wider string enum without a literal "pending" — a
# freshly-created row reads as "matched" until reviewed further downstream.
CANDIDATE_STATUS_MAP = {
    CandidateProfileStatus.PENDING.value: "matched",
    CandidateProfileStatus.MATCHED.value: "matched",
    CandidateProfileStatus.APPROVED.value: "approved",
    CandidateProfileStatus.HOLD.value: "hold",
    CandidateProfileStatus.REJECTED.value: "rejected",
}

READINESS_TONE_MAP = {"low": "r", "medium": "a", "high": "g"}


def ready_weeks_min(ready_in: Optional[str]) -> Optional[int]:
    """`ready_in` is a free-form LLM estimate like "4-6 weeks" — pull the
    first number out for the sortable/filterable `ready_weeks_min` field."""
    if not ready_in:
        return None
    match = re.search(r"\d+", ready_in)
    return int(match.group()) if match else None


def serialize_candidate_attributes(profile: CandidateProfile, role_request_id: Optional[UUID]) -> dict[str, Any]:
    """Map a `candidate_profile` row (profile_data JSONB + status int) onto
    the frontend's CandidateAttributes shape. Shared by the shortlist list
    endpoint and the candidate deep-dive detail endpoint."""
    data = profile.profile_data or {}
    readiness_factors = [
        {
            "label": f.get("label"),
            "value": (f.get("level") or "").capitalize(),
            "tone": READINESS_TONE_MAP.get((f.get("level") or "").lower(), "a"),
        }
        for f in data.get("readiness_factors") or []
    ]
    return {
        "role_request_id": str(role_request_id) if role_request_id else None,
        "match_run_id": str(profile.run_ai_match) if profile.run_ai_match else None,
        "employee": {"id": str(profile.user_uuid), "name": data.get("name"), "avatar_url": ""},
        "current_role": data.get("current_role"),
        "department": data.get("department"),
        "location": data.get("location"),
        "tenure_label": data.get("tenure"),
        "current_manager": data.get("current_manager"),
        "match_pct": data.get("match_score"),
        "ready_in_label": data.get("ready_in"),
        "ready_weeks_min": ready_weeks_min(data.get("ready_in")),
        "cost_impact": (data.get("cost_impact") or "").lower() or None,
        "confidence": data.get("confidence"),
        "status": CANDIDATE_STATUS_MAP.get(profile.status, "matched"),
        "ai_summary": data.get("summary"),
        "strengths": data.get("strengths") or [],
        "readiness_factors": readiness_factors,
        "top_evidence": data.get("evidence") or [],
        "top_gaps": data.get("gaps") or [],
        "career_signals": data.get("career_signals") or [],
    }
