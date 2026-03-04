"""Static info endpoint for the Alex Dev agent."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/alex-dev", tags=["alex-dev"])


@router.get("/info")
async def get_alex_dev_info():
    return {
        "agent_id": "alex-dev",
        "name": "Alex Dev",
        "role": "Senior Product Engineer",
        "focus": [
            "rapid prototyping",
            "backend automation",
            "frontend polish",
            "observability",
        ],
        "strengths": [
            "FastAPI backends",
            "workflow orchestration",
            "database-aware metrics",
            "clean API design",
        ],
        "status": "active",
        "contact": {
            "channel": "internal",
            "on_call": False,
        },
        "version": "1.0",
        "notes": "Static profile for dashboard cards and agent intros.",
    }
