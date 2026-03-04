import json
from typing import Any, Dict, List, Optional


def _parse_context(raw_context: Any) -> Dict[str, Any]:
    if isinstance(raw_context, dict):
        return raw_context
    if isinstance(raw_context, str):
        try:
            return json.loads(raw_context)
        except Exception:
            return {}
    return {}


def compute_progress(job: Dict[str, Any], steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute a lightweight progress summary from job context and job_steps."""
    context = _parse_context(job.get("context"))
    plan = context.get("plan") if isinstance(context, dict) else None
    plan_steps = plan.get("steps") if isinstance(plan, dict) else None
    total_steps: Optional[int] = len(plan_steps) if isinstance(plan_steps, list) else None

    major_steps = [
        step for step in steps
        if isinstance(step.get("step_name"), str) and "::" not in step.get("step_name")
    ]
    completed_steps = sum(1 for step in major_steps if step.get("status") == "success")

    current_step = None
    for step in reversed(steps):
        if step.get("status") in ("in_progress", "awaiting_approval"):
            current_step = step.get("step_name")
            break
    if current_step is None and steps:
        current_step = steps[-1].get("step_name")

    percent = None
    if total_steps:
        percent = round((completed_steps / total_steps) * 100, 1)

    return {
        "completed_steps": completed_steps,
        "total_steps": total_steps,
        "percent": percent,
        "current_step": current_step,
        "latest_status": job.get("status"),
    }
