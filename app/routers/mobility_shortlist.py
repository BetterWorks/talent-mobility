from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.candidate_profile import CandidateProfileDAO
from app.db.run_ai_matches import RunAiMatches, RunAiMatchesBase, RunAiMatchesDAO
from app.services.candidate_mapping import serialize_candidate_attributes
from app.worker.tasks import run_ai_match_task


# Router for the Role & AI Shortlist screen. Wired to the real pipeline:
# `match-runs` (POST + latest) reuses the create+dispatch logic from
# POST /api/ai-matches/; `candidates` reuses the read logic from
# GET /api/candidate-profiles/by-run/{run_id}, resolved via the role
# request's latest match run.
router = APIRouter(prefix="/role-requests", tags=["Shortlist"])

# pending/running both read as "running" to the frontend; only a completed
# run unlocks the shortlist table.
_MATCH_STATUS_MAP = {
    "pending": "running",
    "running": "running",
    "completed": "ready",
    "failed": "failed",
}


def _serialize_match_run(run: RunAiMatches) -> dict[str, Any]:
    status = _MATCH_STATUS_MAP.get(run.status, "running")
    attributes: dict[str, Any] = {
        "role_request_id": str(run.request_id) if run.request_id else None,
        "status": status,
    }
    if status == "ready":
        attributes["completed_at"] = run.modified.isoformat() if run.modified else None
    return {"data": {"type": "mobility_match_run", "id": str(run.id), "attributes": attributes}}


@router.post("/{request_id}/match-runs", status_code=202)
async def run_ai_match(request_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Run / Re-Run AI match — same create+dispatch as POST /api/ai-matches/,
    just under the path and JSON:API-shaped response the frontend expects."""
    dao = RunAiMatchesDAO(session)
    run = await dao.create(RunAiMatchesBase(request_id=request_id))
    run_ai_match_task.delay(run_id=str(run.id), request_id=str(request_id))
    return _serialize_match_run(run)


@router.get("/{request_id}/match-runs/latest")
async def get_latest_match_run(request_id: UUID, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    dao = RunAiMatchesDAO(session)
    run = await dao.get_latest_by_request(request_id)
    if not run:
        raise HTTPException(status_code=404, detail="No match run yet")
    return _serialize_match_run(run)


def _parse_bracket_query(request: Request) -> dict[str, Any]:
    """The frontend serializes list params as `filter[q]`, `page[limit]`,
    `sort[0][match_pct]=desc`, etc — FastAPI can't bind those to named
    params, so parse the raw query string instead."""
    filter_params: dict[str, str] = {}
    limit, offset = 20, 0
    sort: list[tuple[str, str]] = []
    for key, value in request.query_params.multi_items():
        if key.startswith("filter[") and key.endswith("]"):
            filter_params[key[len("filter["):-1]] = value
        elif key == "page[limit]":
            limit = int(value)
        elif key == "page[offset]":
            offset = int(value)
        elif key.startswith("sort[") and "][" in key:
            field = key.split("][", 1)[1].rstrip("]")
            sort.append((field, value))
    return {"filter": filter_params, "limit": limit, "offset": offset, "sort": sort}


def _serialize_candidate(request_id: UUID, profile) -> dict[str, Any]:
    return {
        "type": "mobility_candidate",
        "id": str(profile.id),
        "attributes": serialize_candidate_attributes(profile, request_id),
    }


@router.get("/{request_id}/candidates")
async def get_shortlist_candidates(
    request_id: UUID, request: Request, session: AsyncSession = Depends(get_session)
) -> dict[str, Any]:
    """Shortlist rows for the role request's latest match run — same read
    logic as GET /api/candidate-profiles/by-run/{run_id}, resolved here via
    the role request instead of taking a run_id directly."""
    query = _parse_bracket_query(request)

    run_dao = RunAiMatchesDAO(session)
    latest_run = await run_dao.get_latest_by_request(request_id)
    if not latest_run:
        return {"data": [], "included": [], "meta": {"page": {"limit": query["limit"], "offset": 0, "total": 0}}}

    cost_impact = query["filter"].get("cost_impact")
    db_sort_by = "match_score" if any(f == "match_pct" for f, _ in query["sort"]) else (
        "cost_impact" if any(f == "cost_impact" for f, _ in query["sort"]) else None
    )
    db_sort_desc = next((order == "desc" for f, order in query["sort"] if f in ("match_pct", "cost_impact")), True)

    candidate_dao = CandidateProfileDAO(session)
    profiles = await candidate_dao.list_by_run(
        latest_run.id,
        cost_impact=cost_impact.capitalize() if cost_impact else None,
        sort_by=db_sort_by,
        sort_desc=db_sort_desc,
    )

    resources = [_serialize_candidate(request_id, p) for p in profiles]

    search = query["filter"].get("q", "").strip().lower()
    if search:
        resources = [
            r for r in resources
            if search in (r["attributes"]["employee"]["name"] or "").lower()
            or search in (r["attributes"]["current_role"] or "").lower()
        ]

    # ready_weeks_min has no DB-column equivalent (see candidate_mapping.ready_weeks_min)
    # — sort in Python when that's the requested field.
    for field, order in reversed(query["sort"]):
        if field == "ready_weeks_min":
            resources.sort(key=lambda r: r["attributes"]["ready_weeks_min"] or 0, reverse=(order == "desc"))

    total = len(resources)
    page = resources[query["offset"]: query["offset"] + query["limit"]]

    return {
        "data": page,
        "included": [],
        "meta": {"page": {"limit": query["limit"], "offset": query["offset"], "total": total}},
    }
