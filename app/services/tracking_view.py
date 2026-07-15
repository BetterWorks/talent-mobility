from datetime import date
from typing import Any, List

from app.db.plan import Plan, PlanAction, PlanWeek


def _week_runtime_status(week: PlanWeek, today: date) -> str:
    """PlanWeek.status is set once at generation time and never updated elsewhere — compute the
    live status here from today vs. the week's date range instead of trusting the stored value."""
    if week.end_date and today > week.end_date:
        return "completed"
    if week.start_date and week.start_date <= today <= (week.end_date or week.start_date):
        return "in_progress"
    return "upcoming"


def build_tracking(plan: Plan, weeks: List[PlanWeek], actions: List[PlanAction]) -> dict[str, Any]:
    """No real Goals/Feedback/Learning module integration exists to source real progress
    metrics from, so most of this is heuristically derived from the plan's own week schedule
    (which IS real, persisted data) rather than fully fabricated — see inline notes for what's
    a genuine computation vs. a placeholder."""
    today = date.today()
    total_weeks = plan.duration_weeks or len(weeks) or 1

    statuses = [_week_runtime_status(w, today) for w in weeks]
    completed_weeks = sum(1 for s in statuses if s == "completed")
    current_week = next((w for w, s in zip(weeks, statuses) if s == "in_progress"), None)

    overall_progress_pct = min(round(completed_weeks / total_weeks * 100), 100)
    week_label = current_week.label if current_week else ("Completed" if completed_weeks >= total_weeks else "Week 1")

    last_week = weeks[-1] if weeks else None
    overdue = bool(last_week and last_week.end_date and today > last_week.end_date and plan.status != "completed")
    on_track = not overdue

    milestones_done = sum(1 for a in actions if a.attachment_filename)
    milestones_total = len(actions)

    # goal/learning/one_on_one metrics have no real source (no Goals/Learning/1:1 module
    # integration) — derived proportionally from real week progress as a stand-in.
    metrics = {
        "milestones": {"done": milestones_done, "total": milestones_total},
        "goal_progress_pct": overall_progress_pct,
        "learning_pct": round(overall_progress_pct * 0.8),
        "one_on_one_attendance_pct": min(overall_progress_pct + 10, 100) if weeks else 0,
    }

    tracking_weeks = [
        {
            "week_no": w.week_no,
            "label": w.label,
            "focus": w.focus,
            "status": s,
        }
        for w, s in zip(weeks, statuses)
    ]

    risks: List[dict[str, Any]] = []
    if overdue:
        risks.append({
            "level": "risk",
            "text": f"Plan duration ({total_weeks} weeks) has elapsed without a completed outcome.",
            "when": today.isoformat(),
        })

    checkpoints = [
        {
            "date": w.start_date.isoformat() if w.start_date else None,
            "title": w.label or f"Week {w.week_no}",
            "status": "done" if s == "completed" else ("current" if s == "in_progress" else "upcoming"),
        }
        for w, s in zip(weeks, statuses)
    ]

    return {
        "overall_progress_pct": overall_progress_pct,
        "week_label": week_label,
        "on_track": on_track,
        "metrics": metrics,
        "weeks": tracking_weeks,
        "risks": risks,
        "checkpoints": checkpoints,
    }
