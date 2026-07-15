from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.case import Case, CaseDAO, CaseStatus
from app.db.consent import ConsentDAO, ConsentStatus
from app.db.internal_mobility_request import InternalMobilityRequestDAO
from app.db.plan import (
    Plan, PlanAction, PlanActionBase, PlanActionDAO, PlanBase, PlanDAO, PlanStatus, PlanWeek, PlanWeekBase,
    PlanWeekDAO,
)
from app.db.task import TaskBase, TaskDAO
from app.models.plan import PlanGenerateRequest, PlanPatchRequest
from app.services.plan_generation import generate_actions, generate_weeks
from app.utils.common import get_utc_now
from app.utils.exceptions import MobilityApiError


router = APIRouter(prefix="/cases", tags=["Planning"])

_DEFAULT_DURATION_WEEKS = 8


def _serialize_plan(plan: Plan) -> dict[str, Any]:
    return {
        "type": "mobility_plan",
        "id": str(plan.id),
        "attributes": {
            "case_id": str(plan.case_id),
            "status": plan.status,
            "ai_generated": plan.ai_generated,
            "duration_weeks": plan.duration_weeks,
            "start_date": plan.start_date.isoformat() if plan.start_date else None,
            # No real user reference for plan owner (see plan.py's note) — id is synthetic.
            "owner": {"id": str(plan.id), "name": plan.owner_name, "role": "Hiring Manager"},
            "readiness_target": plan.readiness_target,
            "initiated_on": plan.initiated_on.isoformat() if plan.initiated_on else None,
        },
    }


def _serialize_week(week: PlanWeek) -> dict[str, Any]:
    return {
        "type": "mobility_plan_week",
        "id": str(week.id),
        "attributes": {
            "week_no": week.week_no,
            "label": week.label,
            "focus": week.focus,
            "goal": week.goal,
            "one_on_one": week.one_on_one,
            "learning": week.learning,
            "start_date": week.start_date.isoformat() if week.start_date else None,
            "end_date": week.end_date.isoformat() if week.end_date else None,
            "status": week.status,
            "position": week.position,
        },
    }


def _serialize_action(action: PlanAction) -> dict[str, Any]:
    return {
        "type": "mobility_plan_action",
        "id": str(action.id),
        "attributes": {
            "title": action.title,
            "description": action.description,
            "kind": action.kind,
            "module": action.module,
            "deep_link": action.deep_link,
            "linked_entity_id": action.linked_entity_id,
            "linked_status": action.linked_status,
            "attachment_filename": action.attachment_filename,
            "attachment_url": action.attachment_url,
            "position": action.position,
        },
    }


async def _get_case_or_404(session: AsyncSession, case_id: UUID) -> Case:
    case = await CaseDAO(session).get_by_id(case_id)
    if not case:
        raise MobilityApiError(404, "Case not found")
    return case


async def _get_plan_or_404(session: AsyncSession, case_id: UUID) -> Plan:
    plan = await PlanDAO(session).get_by_case(case_id)
    if not plan:
        raise MobilityApiError(404, "No plan yet")
    return plan


@router.get("/{case_id}/plan")
async def get_plan(case_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    plan = await _get_plan_or_404(session, case_id)
    weeks = await PlanWeekDAO(session).list_by_plan(plan.id)
    actions = await PlanActionDAO(session).list_by_plan(plan.id)
    return {
        "data": _serialize_plan(plan),
        "included": [_serialize_week(w) for w in weeks] + [_serialize_action(a) for a in actions],
    }


@router.patch("/{case_id}/plan")
async def update_plan(
    case_id: UUID, body: PlanPatchRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    plan = await _get_plan_or_404(session, case_id)
    plan_dao = PlanDAO(session)

    if body.data.attributes:
        updates = {k: v for k, v in body.data.attributes.model_dump(exclude_unset=True).items() if v is not None}
        # owner_id has no real user directory to resolve against on this side — ignored, plan
        # owner stays whatever it was seeded with (see plan.py's note on denormalized identity).
        updates.pop("owner_id", None)
        if updates:
            plan = await plan_dao.update(plan.id, **updates)

    week_dao = PlanWeekDAO(session)
    if body.data.weeks:
        for week_write in body.data.weeks:
            if not week_write.id:
                continue
            week_updates = {
                k: v for k, v in week_write.attributes.model_dump(exclude_unset=True).items() if v is not None
            }
            if week_updates:
                await week_dao.update(week_write.id, **week_updates)

    weeks = await week_dao.list_by_plan(plan.id)
    actions = await PlanActionDAO(session).list_by_plan(plan.id)
    return {
        "data": _serialize_plan(plan),
        "included": [_serialize_week(w) for w in weeks] + [_serialize_action(a) for a in actions],
    }


@router.post("/{case_id}/plan/generate")
async def generate_plan(
    case_id: UUID, body: PlanGenerateRequest = PlanGenerateRequest(), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    """Rule-based generation (see plan_generation.py) — not a real AI call. Replaces any
    existing weeks/actions with a freshly generated set."""
    case = await _get_case_or_404(session, case_id)
    duration_weeks = (
        (body.data.attributes.duration_weeks if body.data and body.data.attributes else None)
        or _DEFAULT_DURATION_WEEKS
    )

    plan_dao = PlanDAO(session)
    plan = await plan_dao.get_by_case(case_id)
    if plan:
        plan = await plan_dao.update(
            plan.id, status=PlanStatus.DRAFT.value, ai_generated=True, duration_weeks=duration_weeks
        )
    else:
        role_request = await InternalMobilityRequestDAO(session).get_by_id(case.role_request_id)
        plan = await plan_dao.create(
            PlanBase(
                case_id=case_id,
                status=PlanStatus.DRAFT.value,
                ai_generated=True,
                duration_weeks=duration_weeks,
                owner_name=role_request.hiring_manager if role_request else None,
            )
        )

    week_dao, action_dao, task_dao = PlanWeekDAO(session), PlanActionDAO(session), TaskDAO(session)
    await week_dao.delete_by_plan(plan.id)
    await action_dao.delete_by_plan(plan.id)
    await task_dao.delete_by_case(case_id)

    weeks = await week_dao.bulk_create(
        [PlanWeekBase(plan_id=plan.id, **w) for w in generate_weeks(duration_weeks, plan.start_date)]
    )
    actions = await action_dao.bulk_create(
        [PlanActionBase(plan_id=plan.id, **a) for a in generate_actions()]
    )
    # Tasks mirror the redirect-kind actions as "synced" items in their target module — the
    # closest this POC gets to a real Goals/Learning/etc integration (see tracking's task list).
    await task_dao.bulk_create([
        TaskBase(
            case_id=case_id,
            title=a.title,
            module=a.module,
            owner_name=plan.owner_name,
            due_label=f"Week {min(a.position + 1, duration_weeks)}",
            status="created",
        )
        for a in actions
        if a.kind == "redirect"
    ])
    return {
        "data": _serialize_plan(plan),
        "included": [_serialize_week(w) for w in weeks] + [_serialize_action(a) for a in actions],
    }


@router.post("/{case_id}/plan/actions/{action_id}/attach")
async def attach_plan_action(
    case_id: UUID, action_id: UUID, file: UploadFile = File(...), session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    """No real file storage — stubbed as a filename + mock URL, matching the POC scope."""
    action_dao = PlanActionDAO(session)
    action = await action_dao.get_by_id(action_id)
    if not action:
        raise MobilityApiError(404, "Plan action not found")
    action = await action_dao.update(
        action_id, attachment_filename=file.filename, attachment_url=f"/mock-uploads/{case_id}/{file.filename}"
    )
    return {"data": _serialize_action(action)}


@router.delete("/{case_id}/plan/actions/{action_id}/attach", status_code=204)
async def remove_plan_action_attachment(
    case_id: UUID, action_id: UUID, session: AsyncSession = Depends(get_session)
) -> None:
    action_dao = PlanActionDAO(session)
    action = await action_dao.get_by_id(action_id)
    if not action:
        raise MobilityApiError(404, "Plan action not found")
    await action_dao.update(action_id, attachment_filename=None, attachment_url=None)


@router.post("/{case_id}/plan/initiate")
async def initiate_plan(case_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    plan = await _get_plan_or_404(session, case_id)
    week_dao = PlanWeekDAO(session)
    weeks: List[PlanWeek] = await week_dao.list_by_plan(plan.id)
    if not weeks:
        raise MobilityApiError(409, "Generate a transition plan before initiating.")

    consents = await ConsentDAO(session).list_by_case(case_id)
    if not consents or any(c.status != ConsentStatus.RECEIVED.value for c in consents):
        raise MobilityApiError(409, "All participant consents must be received before initiating.")

    plan_dao = PlanDAO(session)
    plan = await plan_dao.update(plan.id, status=PlanStatus.ACTIVE.value, initiated_on=get_utc_now(tz=False))
    await CaseDAO(session).update(case_id, status=CaseStatus.IN_TRANSITION.value)

    actions = await PlanActionDAO(session).list_by_plan(plan.id)
    return {
        "data": _serialize_plan(plan),
        "included": [_serialize_week(w) for w in weeks] + [_serialize_action(a) for a in actions],
    }
