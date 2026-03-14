"""Platform monitoring: system_events (CEO/orchestrator errors). Not development_points (HR flow)."""
import logging
from fastapi import APIRouter, Request, HTTPException, Depends

from app.middleware.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["system-events"])


@router.get("/system-events", dependencies=[Depends(get_current_user)])
async def get_system_events(
    request: Request,
    unresolved_only: bool = False,
    limit: int = 50,
):
    """Alle events, optioneel gefilterd. Voor het platform-overzicht."""
    svc = getattr(request.app.state, "system_events", None)
    if not svc:
        return {"events": [], "count": 0}
    events = await svc.get_events(unresolved_only=unresolved_only, limit=limit)
    return {"events": events, "count": len(events)}


@router.patch("/system-events/{event_id}/resolve", dependencies=[Depends(get_current_user)])
async def resolve_system_event(event_id: str, request: Request):
    """Markeer een event als opgelost (door de menselijke operator)."""
    svc = getattr(request.app.state, "system_events", None)
    if not svc:
        raise HTTPException(status_code=503, detail="System events service not available")
    success = await svc.resolve_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Event niet gevonden of al opgelost")
    return {"resolved": True, "event_id": event_id}
