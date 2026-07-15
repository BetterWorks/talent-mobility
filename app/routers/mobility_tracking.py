from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.plan import PlanActionDAO, PlanDAO, PlanStatus, PlanWeekDAO, PlanWeekStatus
from app.db.task import Task, TaskDAO, TaskSyncStatus
from app.services.tracking_view import build_tracking
from app.utils.common import get_utc_now
from app.utils.exceptions import MobilityApiError


router = APIRouter(prefix="/cases", tags=["Tracking"])


def _serialize_task(task: Task) -> dict[str, Any]:
    return {
        "type": "mobility_task",
        "id": str(task.id),
        "attributes": {
            "title": task.title,
            "module": task.module,
            "owner": {"id": str(task.id), "name": task.owner_name} if task.owner_name else None,
            "due_label": task.due_label,
            "status": task.status,
            "sync_status": task.sync_status,
            "external_ref_id": task.external_ref_id,
        },
    }


@router.get("/{case_id}/tracking")
async def get_tracking(case_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    plan = await PlanDAO(session).get_by_case(case_id)
    if not plan or plan.status not in ("active", "completed"):
        raise MobilityApiError(404, "No tracking data yet — initiate the transition plan first.")

    weeks = await PlanWeekDAO(session).list_by_plan(plan.id)
    actions = await PlanActionDAO(session).list_by_plan(plan.id)
    return {
        "data": {
            "type": "mobility_tracking",
            "id": str(plan.id),
            "attributes": build_tracking(plan, weeks, actions),
        },
    }


@router.post("/{case_id}/tracking/complete")
async def complete_tracking_demo(case_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Demo-only fast-forward: backdates every week into the past and marks every action done,
    so the real progress derivation in tracking_view.build_tracking naturally reports 100% —
    no separate fake "progress" override is introduced, this just ages the underlying data."""
    plan_dao = PlanDAO(session)
    plan = await plan_dao.get_by_case(case_id)
    if not plan or plan.status not in ("active", "completed"):
        raise MobilityApiError(404, "No tracking data yet — initiate the transition plan first.")

    week_dao = PlanWeekDAO(session)
    weeks = await week_dao.list_by_plan(plan.id)
    yesterday = get_utc_now(tz=False).date() - timedelta(days=1)
    for i, week in enumerate(weeks):
        end = yesterday - timedelta(weeks=len(weeks) - 1 - i)
        await week_dao.update(
            week.id, start_date=end - timedelta(days=6), end_date=end, status=PlanWeekStatus.COMPLETED.value
        )

    action_dao = PlanActionDAO(session)
    for action in await action_dao.list_by_plan(plan.id):
        if not action.attachment_filename:
            await action_dao.update(
                action.id, attachment_filename="completed.txt", attachment_url=f"/mock-uploads/{case_id}/completed.txt"
            )

    # Otherwise on_track's overdue check (today > last week's end_date, status != completed)
    # would flag the now-100%-progress plan as "Needs Attention", which would be contradictory.
    plan = await plan_dao.update(plan.id, status=PlanStatus.COMPLETED.value)

    weeks = await week_dao.list_by_plan(plan.id)
    actions = await action_dao.list_by_plan(plan.id)
    return {
        "data": {
            "type": "mobility_tracking",
            "id": str(plan.id),
            "attributes": build_tracking(plan, weeks, actions),
        },
    }


@router.get("/{case_id}/tasks")
async def list_tasks(case_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    tasks = await TaskDAO(session).list_by_case(case_id)
    return {"data": [_serialize_task(t) for t in tasks], "meta": {"page": {"limit": len(tasks), "offset": 0, "total": len(tasks)}}}


@router.post("/{case_id}/tasks/{task_id}/retry-sync")
async def retry_task_sync(case_id: UUID, task_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """No real external sync system exists — retry always reports success."""
    task_dao = TaskDAO(session)
    task = await task_dao.update(task_id, sync_status=TaskSyncStatus.SYNCED.value)
    if not task:
        raise MobilityApiError(404, "Task not found")
    return {"data": _serialize_task(task)}
