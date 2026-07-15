from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request


# Dummy stub router for the Role & AI Shortlist screen — unblocks frontend
# development ahead of the real AI matching pipeline (see ai_matches.py /
# candidate_profiles.py). Everything here is in-memory, canned data; nothing
# is persisted to the database.
router = APIRouter(prefix="/role-requests", tags=["Shortlist"])

_MATCH_RUNS: dict[str, dict[str, Any]] = {}
_MATCH_RUN_WARMUP = timedelta(seconds=15)

_STUB_CANDIDATES: list[dict[str, Any]] = [
    {
        "id": "c1a1a1a1-0000-0000-0000-000000000001",
        "employee": {"name": "Priya Nair", "avatar_url": "", "role": "Senior Business Analyst"},
        "current_role": "Senior Business Analyst",
        "match_pct": 92,
        "ready_in_label": "2–3 weeks",
        "ready_weeks_min": 2,
        "cost_impact": "high",
        "confidence": "High",
        "status": "matched",
        "strengths": ["Stakeholder management", "SQL & data modeling"],
        "top_gaps": ["Executive presentation"],
    },
    {
        "id": "c2b2b2b2-0000-0000-0000-000000000002",
        "employee": {"name": "Daniel Osei", "avatar_url": "", "role": "Product Marketing Manager"},
        "current_role": "Product Marketing Manager",
        "match_pct": 87,
        "ready_in_label": "4–6 weeks",
        "ready_weeks_min": 4,
        "cost_impact": "medium",
        "confidence": "High",
        "status": "review",
        "strengths": ["Go-to-market strategy", "Cross-functional leadership"],
        "top_gaps": ["Pricing analytics"],
    },
    {
        "id": "c3c3c3c3-0000-0000-0000-000000000003",
        "employee": {"name": "Mei Lin Tan", "avatar_url": "", "role": "Data Engineer II"},
        "current_role": "Data Engineer II",
        "match_pct": 81,
        "ready_in_label": "6–8 weeks",
        "ready_weeks_min": 6,
        "cost_impact": "high",
        "confidence": "Medium",
        "status": "matched",
        "strengths": ["Pipeline architecture", "Python"],
        "top_gaps": ["People management"],
    },
    {
        "id": "c4d4d4d4-0000-0000-0000-000000000004",
        "employee": {"name": "Arjun Mehta", "avatar_url": "", "role": "Customer Success Lead"},
        "current_role": "Customer Success Lead",
        "match_pct": 76,
        "ready_in_label": "2–4 weeks",
        "ready_weeks_min": 2,
        "cost_impact": "low",
        "confidence": "Medium",
        "status": "evidence",
        "strengths": ["Client retention", "Onboarding design"],
        "top_gaps": ["Technical scoping"],
    },
    {
        "id": "c5e5e5e5-0000-0000-0000-000000000005",
        "employee": {"name": "Sofia Reyes", "avatar_url": "", "role": "Financial Analyst"},
        "current_role": "Financial Analyst",
        "match_pct": 74,
        "ready_in_label": "8–10 weeks",
        "ready_weeks_min": 8,
        "cost_impact": "medium",
        "confidence": "Low",
        "status": "matched",
        "strengths": ["Forecasting models", "Budget planning"],
        "top_gaps": ["Stakeholder communication"],
    },
    {
        "id": "c6f6f6f6-0000-0000-0000-000000000006",
        "employee": {"name": "Tomasz Nowak", "avatar_url": "", "role": "QA Engineer"},
        "current_role": "QA Engineer",
        "match_pct": 69,
        "ready_in_label": "10–12 weeks",
        "ready_weeks_min": 10,
        "cost_impact": "low",
        "confidence": "Low",
        "status": "hold",
        "strengths": ["Test automation"],
        "top_gaps": ["Domain knowledge", "Leadership experience"],
    },
]


def _match_run_status(run: dict[str, Any]) -> str:
    if datetime.now(timezone.utc) - run["created_at"] >= _MATCH_RUN_WARMUP:
        return "ready"
    return "running"


def _serialize_match_run(request_id: str, run: dict[str, Any]) -> dict[str, Any]:
    status = _match_run_status(run)
    attributes: dict[str, Any] = {
        "role_request_id": request_id,
        "status": status,
        "model_version": "stub-model-v1",
        "prompt_version": "stub-prompt-v1",
        "policy_version": "stub-policy-v1",
        "eligible_count": len(_STUB_CANDIDATES),
        "excluded_count": 3,
    }
    if status == "ready":
        attributes["completed_at"] = run["created_at"].isoformat()
    return {"data": {"type": "mobility_match_run", "id": run["id"], "attributes": attributes}}


@router.post("/{request_id}/match-runs", status_code=202)
async def run_ai_match_stub(request_id: UUID) -> dict[str, Any]:
    """Dummy stub: no real AI matching runs here — the run just "warms up"
    for a few seconds and then reports ready so the frontend polling loop
    (GET .../match-runs/latest) resolves naturally."""
    run = {"id": str(uuid4()), "created_at": datetime.now(timezone.utc)}
    _MATCH_RUNS[str(request_id)] = run
    return _serialize_match_run(str(request_id), run)


@router.get("/{request_id}/match-runs/latest")
async def get_latest_match_run_stub(request_id: UUID) -> dict[str, Any]:
    run = _MATCH_RUNS.get(str(request_id))
    if not run:
        raise HTTPException(status_code=404, detail="No match run yet")
    return _serialize_match_run(str(request_id), run)


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


@router.get("/{request_id}/candidates")
async def get_shortlist_candidates_stub(request_id: UUID, request: Request) -> dict[str, Any]:
    query = _parse_bracket_query(request)
    candidates = list(_STUB_CANDIDATES)

    search = query["filter"].get("q", "").strip().lower()
    if search:
        candidates = [
            c for c in candidates
            if search in c["employee"]["name"].lower() or search in c["current_role"].lower()
        ]

    cost_impact = query["filter"].get("cost_impact")
    if cost_impact:
        candidates = [c for c in candidates if c["cost_impact"] == cost_impact]

    for field, order in reversed(query["sort"]):
        candidates.sort(key=lambda c: c.get(field) or 0, reverse=(order == "desc"))

    total = len(candidates)
    page = candidates[query["offset"]: query["offset"] + query["limit"]]

    data = [
        {
            "type": "mobility_candidate",
            "id": c["id"],
            "attributes": {**{k: v for k, v in c.items() if k != "id"}, "role_request_id": str(request_id)},
        }
        for c in page
    ]
    return {
        "data": data,
        "included": [],
        "meta": {"page": {"limit": query["limit"], "offset": query["offset"], "total": total}},
    }
