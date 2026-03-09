"""
GTM Agent API — Activeer de GTM Agent voor growth, marketing en go-to-market taken.
"""
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.gtm_agent import run_gtm_agent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gtm", tags=["gtm"])


class RunGTMTaskRequest(BaseModel):
    """Request body voor POST /api/gtm/run"""

    job_id: str = Field(..., description="Job ID (bijv. CI-JOB-2026-0001)")
    task_type: str = Field(
        ...,
        description="channel_strategy | content_calendar | trend_research | feedback_synthesis",
    )
    platform: str = Field(
        ...,
        description="wonderz | clawagency | blogable",
    )
    brief: str = Field(..., description="Beschrijving van de taak")
    context: Optional[Dict[str, Any]] = Field(default_factory=dict)
    handoff_context: Optional[Dict[str, Any]] = Field(default=None)


@router.post("/run")
async def run_gtm_task(request: RunGTMTaskRequest) -> Dict[str, Any]:
    """
    Activeer GTM Agent voor een specifieke taak.

    Body:
    {
        "job_id": "CI-JOB-2026-0001",
        "task_type": "channel_strategy|content_calendar|trend_research|feedback_synthesis",
        "platform": "wonderz|clawagency|blogable",
        "brief": "beschrijving van de taak",
        "context": {}  // optioneel
    }
    """
    valid_task_types = {
        "channel_strategy",
        "content_calendar",
        "trend_research",
        "feedback_synthesis",
    }
    valid_platforms = {"wonderz", "clawagency", "blogable"}

    if request.task_type not in valid_task_types:
        raise HTTPException(
            status_code=400,
            detail=f"task_type moet een van zijn: {', '.join(valid_task_types)}",
        )
    if request.platform not in valid_platforms:
        raise HTTPException(
            status_code=400,
            detail=f"platform moet een van zijn: {', '.join(valid_platforms)}",
        )

    try:
        result = await run_gtm_agent(
            job_id=request.job_id,
            task_type=request.task_type,
            platform=request.platform,
            job_brief=request.brief,
            context=request.context,
            handoff_context=request.handoff_context,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception("GTM Agent failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))
