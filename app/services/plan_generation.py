from datetime import date, timedelta
from typing import Any, Optional

from app.db.plan import PlanActionKind, PlanActionModule, PlanWeekStatus


# Rule-based templating, not an LLM call — same reasoning as match-runs/decision-context: no
# reliable external LLM access in this environment. "AI Generated" in the UI is a placeholder
# for a real synthesis call later; ai_generated=True is still set on the plan since the
# structure (phases, cadence) is templated by this service, not hand-authored by the user.
_PHASE_TEMPLATES = [
    {
        "focus": "Onboarding & Context",
        "goal": "Understand team charter, current priorities, and stakeholders",
        "one_on_one": "Intro 1:1 with new manager — expectations and success criteria",
        "learning": "Complete internal systems and tooling onboarding",
    },
    {
        "focus": "Skill Ramp-Up",
        "goal": "Close top identified skill gaps with hands-on work",
        "one_on_one": "Check in on early blockers and access/tooling issues",
        "learning": "Assigned learning path for role-specific gaps",
    },
    {
        "focus": "Early Contribution",
        "goal": "Ship a first small, well-scoped deliverable",
        "one_on_one": "Review first deliverable feedback",
        "learning": "Shadow a senior team member on a live task",
    },
    {
        "focus": "Independent Ownership",
        "goal": "Own a workstream end-to-end with light oversight",
        "one_on_one": "Calibrate on pace and quality expectations",
        "learning": "Deepen domain knowledge via team documentation/runbooks",
    },
    {
        "focus": "Cross-Team Integration",
        "goal": "Build working relationships with adjacent teams",
        "one_on_one": "Discuss cross-team dependencies and communication norms",
        "learning": "Attend adjacent-team syncs relevant to the role",
    },
    {
        "focus": "Full Ownership & Handoff",
        "goal": "Operate at full productivity for the new role",
        "one_on_one": "Formal ramp-up review against readiness target",
        "learning": "Identify next-stage growth areas",
    },
]


def generate_weeks(duration_weeks: int, start_date: Optional[date]) -> list[dict[str, Any]]:
    weeks = []
    base_date = start_date or date.today()
    for i in range(duration_weeks):
        template = _PHASE_TEMPLATES[min(i * len(_PHASE_TEMPLATES) // duration_weeks, len(_PHASE_TEMPLATES) - 1)]
        week_start = base_date + timedelta(weeks=i)
        weeks.append({
            "week_no": i + 1,
            "label": f"Week {i + 1}",
            "focus": template["focus"],
            "goal": template["goal"],
            "one_on_one": template["one_on_one"],
            "learning": template["learning"],
            "start_date": week_start,
            "end_date": week_start + timedelta(days=6),
            "status": PlanWeekStatus.UPCOMING.value,
            "position": i,
        })
    return weeks


def generate_actions() -> list[dict[str, Any]]:
    return [
        {
            "title": "Set 30-60-90 Day Goals",
            "description": "Create goals in the Goals module for the new role.",
            "kind": PlanActionKind.REDIRECT.value,
            "module": PlanActionModule.GOALS.value,
            "deep_link": "/haven/goals?currentView=goals",
            "position": 0,
        },
        {
            "title": "Enroll in Ramp-Up Learning Path",
            "description": "Assign a learning path covering the gaps identified during matching.",
            "kind": PlanActionKind.REDIRECT.value,
            "module": PlanActionModule.LEARNING.value,
            "deep_link": "/haven/learning",
            "position": 1,
        },
        {
            "title": "Attach Signed Transition Checklist",
            "description": "Upload the signed transition/onboarding checklist.",
            "kind": PlanActionKind.ATTACH.value,
            "module": PlanActionModule.RESOURCES.value,
            "position": 2,
        },
        {
            "title": "Attach Current Manager's Handoff Notes",
            "description": "Upload the handoff notes from the candidate's current manager.",
            "kind": PlanActionKind.ATTACH.value,
            "module": PlanActionModule.RESOURCES.value,
            "position": 3,
        },
    ]
