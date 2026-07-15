from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.candidate_profile import CandidateProfile, CandidateProfileDAO, CandidateProfileStatus
from app.db.case import CaseBase, CaseDAO
from app.db.decision import DecisionBase, DecisionDAO, DecisionOutcome
from app.db.evidence_request import EvidenceRequest, EvidenceRequestBase, EvidenceRequestDAO, EvidenceRequestStatus
from app.db.internal_mobility_request import InternalMobilityRequest, InternalMobilityRequestDAO
from app.db.run_ai_matches import RunAiMatchesDAO
from app.models.decision_review import DecisionCreateRequest, EvidenceCreateRequest, EvidencePatchRequest
from app.routers.user_directory import get_user_details
from app.services.candidate_mapping import CANDIDATE_STATUS_MAP, ready_weeks_min


# Router for the Decision Review screen. No `/candidates` or `/evidence-requests` prefix —
# routes span both bases (see openapi.yaml's Decision + Evidence tags), so each path is given
# in full. Decision/Evidence/Case are all newly modeled here (see better_sense_schema.sql);
# Activity has no dedicated table and is derived on read from the others' timestamps.
router = APIRouter(tags=["Decision"])

_REASON_REQUIRED_OUTCOMES = {
    DecisionOutcome.HOLD.value,
    DecisionOutcome.REJECT.value,
    DecisionOutcome.PROCEED_EXTERNAL.value,
}


async def _get_candidate_or_404(session: AsyncSession, cm_id: UUID) -> CandidateProfile:
    profile = await CandidateProfileDAO(session).get_by_id(cm_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return profile


async def _resolve_role_request(
    session: AsyncSession, profile: CandidateProfile
) -> tuple[Optional[UUID], Optional[InternalMobilityRequest]]:
    if not profile.run_ai_match:
        return None, None
    run = await RunAiMatchesDAO(session).get_by_id(profile.run_ai_match)
    if not run or not run.request_id:
        return None, None
    role_request = await InternalMobilityRequestDAO(session).get_by_id(run.request_id)
    return run.request_id, role_request


def _person_ref(profile: CandidateProfile) -> dict[str, Any]:
    details = get_user_details(profile.user_uuid)
    prof = details["profile"] if details else {}
    return {"id": str(profile.user_uuid), "name": prof.get("name"), "avatar_url": "", "role": prof.get("role")}


def _recommendation(data: dict[str, Any]) -> dict[str, Any]:
    """Rule-based, not an LLM call — same reasoning as the match-runs endpoints: no reliable
    external LLM access in this environment. Placeholder for a real synthesis call later."""
    match_pct = data.get("match_score") or 0
    if match_pct >= 80:
        headline = "Strong internal fit — recommend redeploy"
    elif match_pct >= 60:
        headline = "Moderate fit — consider with a ramp-up plan"
    else:
        headline = "Limited fit — recommend comparing with an external hire"
    strengths, gaps = len(data.get("strengths") or []), len(data.get("gaps") or [])
    detail = (
        f"{match_pct}% match with {strengths} matched strength(s) and {gaps} gap(s) identified. "
        f"AI confidence: {data.get('confidence') or 'Medium'}."
    )
    return {"headline": headline, "detail": detail}


_RETENTION_BY_CONFIDENCE = {
    "High": "Likely positive — strong internal trust and tenure",
    "Medium": "Neutral — monitor through the ramp-up period",
    "Low": "Uncertain — limited signal on retention",
}


def _impact_summary(role_request: Optional[InternalMobilityRequest], data: dict[str, Any]) -> dict[str, Any]:
    estimated_savings = None
    if role_request and role_request.external_hiring_cost:
        # Same 0.67 heuristic as GET /role-requests/{id}/benchmarks — sharing one assumption
        # rather than inventing a second, since neither is backed by real cost accounting yet.
        estimated_savings = {
            "currency": role_request.budget_currency or "USD",
            "amount": round(float(role_request.external_hiring_cost) * 0.67, 2),
        }
    weeks = ready_weeks_min(data.get("ready_in"))
    time_saved_days = None
    if role_request and role_request.hiring_estimate_in_days and weeks is not None:
        time_saved_days = max(role_request.hiring_estimate_in_days - weeks * 7, 0)
    return {
        "estimated_savings": estimated_savings,
        "time_saved_days": time_saved_days,
        "ramp_up": data.get("ready_in"),
        "retention_impact": _RETENTION_BY_CONFIDENCE.get(data.get("confidence") or "Medium"),
    }


@router.get("/candidates/{cm_id}/decision-context")
async def get_decision_context(cm_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    profile = await _get_candidate_or_404(session, cm_id)
    data = profile.profile_data or {}
    _, role_request = await _resolve_role_request(session, profile)
    return {
        "data": {
            "type": "mobility_decision_context",
            "id": str(profile.id),
            "attributes": {
                "candidate": _person_ref(profile),
                "recommendation": _recommendation(data),
                "impact_summary": _impact_summary(role_request, data),
            },
        },
    }


_SCENARIO_SOURCE_REAL = "Role request + AI match data"
_SCENARIO_SOURCE_ASSUMED = "Qualitative assumption"


@router.get("/candidates/{cm_id}/scenarios")
async def get_scenarios(cm_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    profile = await _get_candidate_or_404(session, cm_id)
    data = profile.profile_data or {}
    _, role_request = await _resolve_role_request(session, profile)

    external_cost = (
        float(role_request.external_hiring_cost) if role_request and role_request.external_hiring_cost else None
    )
    currency = (role_request.budget_currency if role_request else None) or "USD"
    savings = _impact_summary(role_request, data)["estimated_savings"]

    rows = [
        {
            "dimension": "Cost",
            "internal": f"{currency} {savings['amount']:,.0f} saved" if savings else "—",
            "external": f"{currency} {external_cost:,.0f}" if external_cost else "—",
            "source": _SCENARIO_SOURCE_REAL if external_cost else _SCENARIO_SOURCE_ASSUMED,
        },
        {
            "dimension": "Time to Fill",
            "internal": data.get("ready_in") or "—",
            "external": (
                f"{role_request.hiring_estimate_in_days} days"
                if role_request and role_request.hiring_estimate_in_days
                else "—"
            ),
            "source": _SCENARIO_SOURCE_REAL,
        },
        {
            "dimension": "Confidence / Risk",
            "internal": data.get("confidence") or "Medium",
            "external": "Unknown (new hire)",
            "source": "AI match confidence",
        },
        {
            "dimension": "Team Continuity",
            "internal": "Retains institutional knowledge",
            "external": "Ramp-up required for a new hire",
            "source": _SCENARIO_SOURCE_ASSUMED,
        },
    ]
    return {
        "data": {
            "type": "mobility_scenario",
            "id": str(profile.id),
            "attributes": {
                "assumptions_source": _SCENARIO_SOURCE_REAL,
                "assumptions_updated_on": (
                    role_request.modified.date().isoformat() if role_request and role_request.modified else None
                ),
                "rows": rows,
            },
        },
    }


def _serialize_evidence(evidence: EvidenceRequest) -> dict[str, Any]:
    return {
        "type": "mobility_evidence_request",
        "id": str(evidence.id),
        "attributes": {
            "candidate_match_id": str(evidence.candidate_match_id),
            "evidence_type": evidence.evidence_type,
            # assignee_id comes from Haven's org-wide identity search (BWUserIdentityAutoComplete),
            # not our local user_directory stub — we only have the id, so name is left blank.
            "assignee": {"id": str(evidence.assignee_id), "name": None, "avatar_url": ""},
            "due_date": evidence.due_date.isoformat() if evidence.due_date else None,
            "status": evidence.status,
            "response": evidence.response,
            "requested_on": evidence.created.isoformat() if evidence.created else None,
        },
    }


@router.get("/candidates/{cm_id}/evidence-requests")
async def list_evidence_requests(cm_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    await _get_candidate_or_404(session, cm_id)
    requests = await EvidenceRequestDAO(session).list_by_candidate(cm_id)
    data = [_serialize_evidence(r) for r in requests]
    return {"data": data, "meta": {"page": {"limit": len(data), "offset": 0, "total": len(data)}}}


@router.post("/candidates/{cm_id}/evidence-requests", status_code=201)
async def ask_for_evidence(
    cm_id: UUID, body: EvidenceCreateRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    await _get_candidate_or_404(session, cm_id)
    attrs = body.data.attributes
    evidence = await EvidenceRequestDAO(session).create(
        EvidenceRequestBase(
            candidate_match_id=cm_id,
            evidence_type=attrs.evidence_type,
            assignee_id=attrs.assignee_id,
            due_date=attrs.due_date,
            note=attrs.note,
        )
    )
    return {"data": _serialize_evidence(evidence)}


@router.patch("/evidence-requests/{ev_id}")
async def update_evidence_request(
    ev_id: UUID, body: EvidencePatchRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    attrs = body.data.attributes
    updates = {k: v for k, v in attrs.model_dump(exclude_unset=True).items() if v is not None}
    evidence = await EvidenceRequestDAO(session).update(ev_id, **updates)
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence request not found")
    return {"data": _serialize_evidence(evidence)}


@router.get("/candidates/{cm_id}/activity")
async def get_activity(cm_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Derived on read from candidate_profile/decision/evidence_request timestamps — no
    dedicated activity_log table (see plan discussion: cheaper now, at the cost of losing
    freeform detail we never stored and of re-deriving on every read)."""
    profile = await _get_candidate_or_404(session, cm_id)
    entries: List[dict[str, Any]] = []

    if profile.created:
        entries.append({
            "actor": {"id": "ai-match-engine", "name": "AI Match Engine", "avatar_url": ""},
            "action": "AI Shortlisted",
            "detail": "Candidate added to the shortlist by the AI matching run.",
            "occurred_on": profile.created,
        })
    if profile.status == CandidateProfileStatus.DECISION.value and profile.modified:
        entries.append({
            "actor": None,
            "action": "Moved to Decision",
            "detail": "Candidate moved to the Decision stage.",
            "occurred_on": profile.modified,
        })

    for evidence in await EvidenceRequestDAO(session).list_by_candidate(cm_id):
        label = evidence.evidence_type.replace("_", " ").title()
        entries.append({
            "actor": None,
            "action": "Evidence Requested",
            "detail": f"{label} requested.",
            "occurred_on": evidence.created,
        })
        if evidence.status != EvidenceRequestStatus.PENDING.value and evidence.modified != evidence.created:
            entries.append({
                "actor": None,
                "action": f"Evidence {evidence.status.title()}",
                "detail": f"{label} marked {evidence.status}.",
                "occurred_on": evidence.modified,
            })

    decision = await DecisionDAO(session).get_latest_by_candidate(cm_id)
    if decision:
        entries.append({
            "actor": None,
            "action": f"Decision: {decision.outcome.title()}",
            "detail": decision.note or f"Outcome recorded: {decision.outcome}.",
            "occurred_on": decision.created,
        })

    entries.sort(key=lambda e: e["occurred_on"] or profile.created, reverse=True)
    data = [
        {
            "type": "mobility_activity",
            "id": f"{cm_id}-{i}",
            "attributes": {**e, "occurred_on": e["occurred_on"].isoformat() if e["occurred_on"] else None},
        }
        for i, e in enumerate(entries)
    ]
    return {"data": data, "meta": {"page": {"limit": len(data), "offset": 0, "total": len(data)}}}


@router.post("/candidates/{cm_id}/decision")
async def record_decision(
    cm_id: UUID, body: DecisionCreateRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    """approve keeps candidate status at `decision` and creates a mobility_case (returned as
    `case_id`) so the frontend can move on to Consent. hold/reject/proceed_external require a
    reason_code and move the candidate to hold/rejected respectively."""
    profile = await _get_candidate_or_404(session, cm_id)
    attrs = body.data.attributes
    outcome = attrs.outcome

    valid_outcomes = {o.value for o in DecisionOutcome}
    if outcome not in valid_outcomes:
        raise HTTPException(status_code=400, detail=f"Invalid outcome: {outcome}")
    if outcome in _REASON_REQUIRED_OUTCOMES and not attrs.reason_code:
        raise HTTPException(status_code=400, detail="reason_code is required for hold/reject/proceed_external")
    if outcome == DecisionOutcome.APPROVE.value and profile.status != CandidateProfileStatus.DECISION.value:
        raise HTTPException(status_code=400, detail="Candidate must be in the Decision stage to approve")

    decision_dao = DecisionDAO(session)
    decision = await decision_dao.create(
        DecisionBase(
            candidate_match_id=cm_id,
            outcome=outcome,
            reason_code=attrs.reason_code,
            note=attrs.note,
            review_date=attrs.review_date,
        )
    )

    candidate_dao = CandidateProfileDAO(session)
    case_id = None
    if outcome == DecisionOutcome.APPROVE.value:
        role_request_id, _ = await _resolve_role_request(session, profile)
        if role_request_id:
            case = await CaseDAO(session).create(
                CaseBase(candidate_match_id=cm_id, role_request_id=role_request_id, decision_id=decision.id)
            )
            case_id = case.id
            decision = await decision_dao.update(decision.id, case_id=case_id)
    elif outcome == DecisionOutcome.HOLD.value:
        profile = await candidate_dao.update(cm_id, status=CandidateProfileStatus.HOLD.value)
    else:  # reject / proceed_external
        profile = await candidate_dao.update(cm_id, status=CandidateProfileStatus.REJECTED.value)

    return {
        "data": {
            "type": "mobility_decision",
            "id": str(decision.id),
            "attributes": {
                "candidate_match_id": str(cm_id),
                "outcome": decision.outcome,
                "reason_code": decision.reason_code,
                "note": decision.note,
                "review_date": decision.review_date.isoformat() if decision.review_date else None,
                "evidence_snapshot_id": None,
                "candidate_status": CANDIDATE_STATUS_MAP.get(profile.status, "matched"),
                "case_id": str(case_id) if case_id else None,
            },
        },
    }
