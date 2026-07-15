from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.candidate_profile import CandidateProfileDAO
from app.db.case import Case, CaseDAO, CaseStatus
from app.db.internal_mobility_request import InternalMobilityRequestDAO
from app.db.learning_proposal import LearningProposal, LearningProposalDAO, LearningProposalStatus
from app.db.outcome_checkpoint import OutcomeCheckpoint, OutcomeCheckpointBase, OutcomeCheckpointDAO
from app.db.plan import PlanDAO
from app.models.outcomes import CloseRequest, OutcomeCheckpointCreateRequest, OutcomeDecisionRequest
from app.routers.user_directory import get_user_details
from app.services.outcomes_view import build_outcomes
from app.utils.exceptions import MobilityApiError


router = APIRouter(prefix="/cases", tags=["Outcomes"])

_OUTCOME_DECISION_ACTIONS = {"confirm_transition", "hold", "extend_plan", "return_prior_role", "escalate_hrbp"}
_ACTIONS_REQUIRING_GOVERNANCE_ACK = _OUTCOME_DECISION_ACTIONS - {"extend_plan"}

_DECISION_STATUS_MAP = {
    "confirm_transition": CaseStatus.COMPLETED.value,
    "return_prior_role": CaseStatus.DECLINED.value,
    "escalate_hrbp": CaseStatus.AT_RISK.value,
}


def _serialize_case(case: Case) -> dict[str, Any]:
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


def _serialize_checkpoint(checkpoint: OutcomeCheckpoint) -> dict[str, Any]:
    return {
        "type": "mobility_outcome_checkpoint",
        "id": str(checkpoint.id),
        "attributes": {
            "checkpoint": checkpoint.checkpoint,
            "dimension": checkpoint.dimension,
            "value": checkpoint.value,
            "source": checkpoint.source,
            "event_date": checkpoint.event_date.isoformat(),
            "is_manual": checkpoint.is_manual,
        },
    }


def _serialize_learning_proposal(proposal: LearningProposal, content: dict[str, Any]) -> dict[str, Any]:
    return {"data": {"type": "mobility_learning_proposal", "id": str(proposal.id), "attributes": {**content, "status": proposal.status}}}


async def _get_case_or_404(session: AsyncSession, case_id: UUID) -> Case:
    case = await CaseDAO(session).get_by_id(case_id)
    if not case:
        raise MobilityApiError(404, "Case not found")
    return case


@router.get("/{case_id}/outcomes")
async def get_outcomes(case_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    case = await _get_case_or_404(session, case_id)
    profile = await CandidateProfileDAO(session).get_by_id(case.candidate_match_id)
    if not profile:
        raise MobilityApiError(404, "Candidate not found")
    role_request = await InternalMobilityRequestDAO(session).get_by_id(case.role_request_id)
    plan = await PlanDAO(session).get_by_case(case_id)

    details = get_user_details(profile.user_uuid)
    candidate_name = details["profile"].get("name") if details else None

    completed_cases = await CaseDAO(session).list_by_statuses([CaseStatus.COMPLETED.value, CaseStatus.CLOSED.value])
    completed_costs: List[Optional[float]] = []
    for c in completed_cases:
        rr = await InternalMobilityRequestDAO(session).get_by_id(c.role_request_id)
        completed_costs.append(float(rr.external_hiring_cost) if rr and rr.external_hiring_cost else None)

    attributes = build_outcomes(profile, candidate_name, role_request, plan, completed_costs)
    return {"data": {"type": "mobility_outcome", "id": str(case.id), "attributes": attributes}}


@router.get("/{case_id}/outcomes/checkpoints")
async def list_outcome_checkpoints(case_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    checkpoints = await OutcomeCheckpointDAO(session).list_by_case(case_id)
    return {
        "data": [_serialize_checkpoint(c) for c in checkpoints],
        "meta": {"page": {"limit": len(checkpoints), "offset": 0, "total": len(checkpoints)}},
    }


@router.post("/{case_id}/outcomes/checkpoints", status_code=201)
async def record_outcome_checkpoint(
    case_id: UUID, body: OutcomeCheckpointCreateRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    await _get_case_or_404(session, case_id)
    attrs = body.data.attributes
    checkpoint = await OutcomeCheckpointDAO(session).create(
        OutcomeCheckpointBase(
            case_id=case_id,
            checkpoint=attrs.checkpoint,
            dimension=attrs.dimension,
            value=attrs.value,
            source=attrs.source,
            event_date=attrs.event_date,
            is_manual=attrs.is_manual if attrs.is_manual is not None else True,
        )
    )
    return {"data": _serialize_checkpoint(checkpoint)}


@router.post("/{case_id}/outcomes/decision")
async def record_outcome_decision(
    case_id: UUID, body: OutcomeDecisionRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    case = await _get_case_or_404(session, case_id)
    attrs = body.data.attributes
    action = attrs.action

    if action not in _OUTCOME_DECISION_ACTIONS:
        raise MobilityApiError(400, f"Invalid action: {action}")
    if action in _ACTIONS_REQUIRING_GOVERNANCE_ACK and not attrs.governance_ack:
        raise MobilityApiError(400, "governance_ack is required for this action")

    case_dao = CaseDAO(session)
    if action == "extend_plan":
        plan = await PlanDAO(session).get_by_case(case_id)
        if plan and plan.duration_weeks:
            await PlanDAO(session).update(plan.id, duration_weeks=plan.duration_weeks + 2)
    else:
        new_status = _DECISION_STATUS_MAP.get(action)
        if new_status:
            case = await case_dao.update(case_id, status=new_status)

    return _serialize_case(case)


@router.post("/{case_id}/close")
async def close_case(
    case_id: UUID, body: CloseRequest = CloseRequest(), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    await _get_case_or_404(session, case_id)
    governance_ack = bool(body.data.attributes.governance_ack) if body.data and body.data.attributes else False
    if not governance_ack:
        raise MobilityApiError(400, "governance_ack is required to close the request")
    case = await CaseDAO(session).update(case_id, status=CaseStatus.CLOSED.value)
    return _serialize_case(case)


@router.post("/{case_id}/outcomes/export-brief")
async def export_executive_brief(case_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """No real report-generation/export service exists — always reports "queued" (no url) rather
    than fabricating a document. The frontend already handles this no-url case."""
    await _get_case_or_404(session, case_id)
    return {"data": {"type": "mobility_export", "attributes": {"url": None}}}


async def _build_learning_proposal_content(session: AsyncSession, case: Case) -> dict[str, Any]:
    """Rule-based content, not a real ML retrospective — same reasoning as decision-context /
    tracking: no reliable external LLM/analytics access in this environment."""
    plan = await PlanDAO(session).get_by_case(case.id)
    role_request = await InternalMobilityRequestDAO(session).get_by_id(case.role_request_id)
    predicted_days = role_request.hiring_estimate_in_days if role_request else None
    return {
        "prediction_vs_actual": (
            [{
                "metric": "Time to Fill",
                "predicted": f"{predicted_days} days" if predicted_days else "—",
                "actual": f"{plan.duration_weeks * 7} days" if plan and plan.duration_weeks else "In progress",
            }]
            if role_request
            else []
        ),
        "proposed_adjustments": [
            "Weight recent project evidence slightly higher for readiness scoring.",
            "Shorten default ramp-up plan duration for high-confidence matches.",
        ],
        "expected_benefit": "Faster time-to-productivity estimates for future internal moves.",
        "risk": "Low — shadow evaluation only, no production scoring change.",
        "affected_roles": "Future internal mobility matches of similar seniority.",
        "rollback_version": "v1.0",
        "evaluation": "Offline backtest against completed cases before any production rollout.",
    }


@router.get("/{case_id}/learning-proposal")
async def get_learning_proposal(case_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    case = await _get_case_or_404(session, case_id)
    proposal = await LearningProposalDAO(session).get_or_create(case_id)
    content = await _build_learning_proposal_content(session, case)
    return _serialize_learning_proposal(proposal, content)


@router.post("/{case_id}/learning-proposal/approve")
async def approve_learning_proposal(case_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    case = await _get_case_or_404(session, case_id)
    proposal_dao = LearningProposalDAO(session)
    proposal = await proposal_dao.get_or_create(case_id)
    proposal = await proposal_dao.update(proposal.id, status=LearningProposalStatus.APPROVED_OFFLINE.value)
    content = await _build_learning_proposal_content(session, case)
    return _serialize_learning_proposal(proposal, content)
