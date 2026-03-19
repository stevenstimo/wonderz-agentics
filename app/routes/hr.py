"""HR API stub — development-points, training-requests, report, notifications, approve-training."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/hr", tags=["hr"])


@router.get("/training-requests")
async def list_training_requests():
    return {"training_requests": []}


@router.post("/approve-training")
async def approve_training():
    return {"ok": True}


@router.get("/development-points")
async def list_development_points():
    return {"development_points": []}


@router.get("/development-points/awaiting-approval")
async def list_development_points_awaiting_approval():
    return []


@router.get("/report")
async def get_report():
    return {}


@router.get("/cross-training-proposals")
async def list_cross_training_proposals():
    return []


@router.get("/notifications")
async def list_notifications():
    return {"notifications": []}


@router.post("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    return {"ok": True}


@router.post("/scan")
async def trigger_scan():
    return {"ok": True}


@router.patch("/development-points/{point_id}")
async def update_development_point(point_id: str):
    return {"ok": True}


@router.post("/development-points/{point_id}/resolve")
async def resolve_development_point(point_id: str):
    return {"ok": True}


@router.post("/cross-train")
async def cross_train():
    return {"ok": True}
