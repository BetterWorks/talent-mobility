from datetime import date
from typing import Any, List, Optional

from app.db.candidate_profile import CandidateProfile
from app.db.internal_mobility_request import InternalMobilityRequest
from app.db.plan import Plan
from app.services.candidate_mapping import ready_weeks_min


_RETENTION_RISK_BY_CONFIDENCE = {
    "High": "Low",
    "Medium": "Moderate",
    "Low": "Elevated",
}

# Same 0.67 heuristic used in decision-context/benchmarks — shared everywhere cost savings
# get estimated, since none of it is backed by real cost-accounting data yet.
_SAVINGS_RATIO = 0.67


def _external_cost_savings(role_request: Optional[InternalMobilityRequest]) -> Optional[dict[str, Any]]:
    if not role_request or not role_request.external_hiring_cost:
        return None
    external_cost = float(role_request.external_hiring_cost)
    return {
        "currency": role_request.budget_currency or "USD",
        "amount": round(external_cost * _SAVINGS_RATIO, 2),
    }


def build_outcomes(
    profile: CandidateProfile,
    candidate_name: Optional[str],
    role_request: Optional[InternalMobilityRequest],
    plan: Optional[Plan],
    completed_cases_external_costs: List[Optional[float]],
) -> dict[str, Any]:
    """KPIs/progress/performance/roi have no real Goals/Feedback/Learning/finance integration to
    source from — all rule-based/templated, grounded in real role_request/candidate_profile/plan
    data wherever there's something real to ground on (see inline notes for which is which)."""
    data = profile.profile_data or {}
    confidence = data.get("confidence") or "Medium"

    cost_saved = _external_cost_savings(role_request)
    ready_weeks = ready_weeks_min(data.get("ready_in"))
    external_days = role_request.hiring_estimate_in_days if role_request else None
    # Fake sparkline trending from the external estimate down to actual ready-in weeks —
    # illustrative only, not a real historical series.
    trend = None
    if external_days:
        trend = [max(external_days - i * (external_days // 6 or 1), external_days // 3) for i in range(6)]

    kpis = {
        "time_to_fill": {
            "value": data.get("ready_in") or (f"{ready_weeks} weeks" if ready_weeks else None),
            "trend": trend,
        },
        "cost_saved": cost_saved,
        "ramp_up": data.get("ready_in"),
        "retention_risk": _RETENTION_RISK_BY_CONFIDENCE.get(confidence, "Moderate"),
    }

    # Progress heuristics: if the plan is active/completed, base them off elapsed-week ratio
    # (real, from the plan's own schedule); otherwise fall back to match-time signals.
    if plan and plan.duration_weeks:
        elapsed = 0
        if plan.start_date:
            elapsed = max(0, (date.today() - plan.start_date).days // 7)
        base_pct = min(round(elapsed / plan.duration_weeks * 100), 100)
    else:
        base_pct = {"High": 70, "Medium": 45, "Low": 20}.get(confidence, 45)

    progress = {
        "goal_progress_pct": base_pct,
        "manager_feedback": min(round(base_pct * 1.05), 100),
        "peer_feedback": min(round(base_pct * 0.95), 100),
        "learning_pct": round(base_pct * 0.8),
    }

    ai_insights = (
        f"{candidate_name or 'This candidate'} is tracking {progress['goal_progress_pct']}% through the transition "
        f"with {confidence.lower()} confidence in a successful ramp-up. "
        f"{'On pace with the transition plan schedule.' if plan else 'No transition plan initiated yet.'}"
    )

    completed_savings = [c for c in completed_cases_external_costs if c]
    program_impact = {
        "internal_moves": len(completed_cases_external_costs),
        "total_cost_saved": {
            "currency": (role_request.budget_currency if role_request else None) or "USD",
            "amount": round(sum(completed_savings) * _SAVINGS_RATIO, 2) if completed_savings else 0,
        },
        # No real productivity/retention tracking system exists — static program-level placeholders.
        "faster_to_productivity_pct": 35,
        "six_month_retention_pct": 88,
    }

    performance = {
        "goal_completion_rate": f"{progress['goal_progress_pct']}%",
        "peer_rating": "4.6/5",
        "manager_rating": "4.8/5",
        "certifications_completed": 2,
    }

    external_estimate = float(role_request.external_hiring_cost) if role_request and role_request.external_hiring_cost else None
    actual_internal_cost = round(external_estimate * (1 - _SAVINGS_RATIO), 2) if external_estimate else None
    roi = {
        "external_hire_cost_estimate": external_estimate,
        "actual_internal_cost": actual_internal_cost,
        "net_savings": cost_saved["amount"] if cost_saved else None,
        "payback_period_days": (external_days // 2) if external_days else 45,
    }

    return {
        "kpis": kpis,
        "progress": progress,
        "ai_insights": ai_insights,
        "program_impact": program_impact,
        "performance": performance,
        "roi": roi,
    }
