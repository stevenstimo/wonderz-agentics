"""Explainer content endpoints."""

import os
from datetime import datetime, timezone
from typing import Dict, Any, List
from fastapi import APIRouter

router = APIRouter(prefix="/api/explainer", tags=["explainer"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_sections() -> List[Dict[str, Any]]:
    updated_at = _now_iso()
    return [
        {
            "slug": "how-it-works",
            "title": "How it works",
            "body_markdown": """
The platform turns an idea into a coordinated delivery plan and then executes it with specialist agents.

- Intake: capture goals, constraints, and success metrics.
- Orchestration: translate the brief into a concrete plan with milestones and owners.
- Execution: agents run tasks, report progress, and surface risks.
- Review: outcomes are validated, logged, and fed back into training.

Use the Job Center to track what changed and the Approval dashboard to approve high-impact training.""".strip(),
            "updated_at": updated_at,
        },
        {
            "slug": "persona",
            "title": "Persona",
            "body_markdown": """
Each agent has a clear persona so outputs stay consistent and explainable.

- Role: what the agent is responsible for.
- Scope: what it should never do without approval.
- Knowledge: the tools and sources it is allowed to use.
- Voice: the tone used in deliverables and updates.

Persona discipline keeps handoffs clean and reduces rework.""".strip(),
            "updated_at": updated_at,
        },
        {
            "slug": "crew",
            "title": "Crew",
            "body_markdown": """
The crew is the active set of agents assigned to current work.

- Crew members are selected based on the brief and required skills.
- Each member has a status, a current task, and a progress signal.
- Training requests are raised when a gap is detected.

Keep an eye on the Crew view to see who is doing what.""".strip(),
            "updated_at": updated_at,
        },
    ]


@router.get("/sections")
async def list_sections():
    sections = _build_sections()
    return {
        "sections": sections,
        "meta": {
            "deploy_env": os.getenv("DEPLOY_ENV", "local"),
            "build_sha": os.getenv("DEPLOY_SHA", os.getenv("GIT_SHA", "unknown")),
            "data_refreshed_at": _now_iso(),
        },
    }
