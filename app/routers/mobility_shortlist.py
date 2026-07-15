from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db import get_session
from app.db.candidate_profile import CandidateProfileDAO
from app.db.internal_mobility_request import InternalMobilityRequestDAO
from app.db.run_ai_matches import RunAiMatches, RunAiMatchesBase, RunAiMatchesDAO, RunAiMatchesStatus
from app.models.match_run import MatchRunAttributes, MatchRunDetailResponse, MatchRunResource, MatchRunStatus, ResourceMeta
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
    RunAiMatchesStatus.PENDING.value: MatchRunStatus.RUNNING,
    RunAiMatchesStatus.RUNNING.value: MatchRunStatus.RUNNING,
    RunAiMatchesStatus.COMPLETED.value: MatchRunStatus.READY,
    RunAiMatchesStatus.FAILED.value: MatchRunStatus.FAILED,
}


def _serialize_match_run(run: RunAiMatches) -> MatchRunDetailResponse:
    status = _MATCH_STATUS_MAP.get(run.status, MatchRunStatus.RUNNING)
    return MatchRunDetailResponse(
        data=MatchRunResource(
            id=run.id,
            meta=ResourceMeta(created_on=run.created, modified_on=run.modified),
            attributes=MatchRunAttributes(
                role_request_id=run.request_id,
                status=status,
                # model/prompt/policy version and eligible/excluded counts aren't
                # tracked yet — left unset rather than faked, since the frontend
                # doesn't render them on this page today.
                completed_at=run.modified if status == MatchRunStatus.READY else None,
            ),
        ),
    )


@router.post("/{request_id}/match-runs", status_code=202, response_model=MatchRunDetailResponse)
async def run_ai_match(request_id: UUID, session: AsyncSession = Depends(get_session)) -> MatchRunDetailResponse:
    """Run / Re-Run AI match — same create+dispatch as POST /api/ai-matches/,
    just under the path and JSON:API-shaped response the frontend expects."""
    dao = RunAiMatchesDAO(session)
    run = await dao.create(RunAiMatchesBase(request_id=request_id))
    run_ai_match_task.delay(run_id=str(run.id), request_id=str(request_id))
    return _serialize_match_run(run)


@router.get("/{request_id}/match-runs/latest", response_model=MatchRunDetailResponse)
async def get_latest_match_run(
    request_id: UUID, session: AsyncSession = Depends(get_session)
) -> MatchRunDetailResponse:
    """Pure read — 404s when no run exists yet so the frontend lands on its
    empty state ("Run AI Match"). Triggering a run is POST's job only; a GET
    must not have the side effect of creating one."""
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


def _serialize_candidate(request_id: UUID, profile, max_salary=None) -> dict[str, Any]:
    return {
        "type": "mobility_candidate",
        "id": str(profile.id),
        "attributes": serialize_candidate_attributes(profile, request_id, max_salary),
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

    request = await InternalMobilityRequestDAO(session).get_by_id(request_id)
    max_salary = request.max_salary if request else None
    resources = [_serialize_candidate(request_id, p, max_salary) for p in profiles]

    # Shortlist-level aggregates for the UI header (over the full shortlist,
    # before any search/pagination narrowing).
    total_matched = len(resources)
    cost_diffs = [
        r["attributes"]["cost_difference"] for r in resources
        if r["attributes"]["cost_difference"] is not None
    ]
    max_saving = max(cost_diffs) if cost_diffs else None

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
        "meta": {
            "page": {"limit": query["limit"], "offset": query["offset"], "total": total},
            "total_matched_profiles": total_matched,
            "max_saving": max_saving,
        },
    }
