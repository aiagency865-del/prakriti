import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core.database import db
from core.security import GOVERNMENT_ROLES, ROAD_STATUSES, get_current_user
from core.ws import manager
from services import _reroute_trips_on_road

router = APIRouter()


class RoadStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    status: str
    reason: str = Field(min_length=3, max_length=500)
    expected_duration: Optional[str] = None


@router.patch("/roads/{road_id}/status")
async def update_road_status(road_id: str, body: RoadStatusUpdate, user: dict = Depends(get_current_user)):
    if user["role"] not in GOVERNMENT_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    new_status = body.status.upper()
    if new_status not in ROAD_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Allowed: {sorted(ROAD_STATUSES)}")
    road = await db.roads.find_one({"id": road_id}, {"_id": 0})
    if not road:
        raise HTTPException(status_code=404, detail="Road not found")
    old_status = road["status"]
    now_iso = datetime.now(timezone.utc).isoformat()
    updates = {
        "status": new_status,
        "status_reason": body.reason,
        "expected_duration": body.expected_duration,
        "updated_at": now_iso,
        "updated_by": user["email"],
    }
    await db.roads.update_one({"id": road_id}, {"$set": updates})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"],
        "official_email": user["email"],
        "official_name": user.get("name"),
        "action_type": "ROAD_STATUS_CHANGE",
        "target_type": "road",
        "target_id": road_id,
        "target_name": road.get("name"),
        "old_state": old_status,
        "new_state": new_status,
        "reason": body.reason,
        "timestamp": now_iso,
    })
    road.update(updates)

    if new_status in ("BLOCKED", "GOVERNMENT_CLOSED"):
        await _reroute_trips_on_road(road_id, road.get("name") or road_id, new_status)
    await manager.broadcast({"type": "ROAD_STATUS_CHANGED", "road_id": road_id, "status": new_status, "road_name": road.get("name")})
    return road


@router.get("/audit")
async def get_audit(limit: int = 50, user: dict = Depends(get_current_user)):
    if user["role"] not in GOVERNMENT_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    return await db.government_actions.find({}, {"_id": 0}).sort("timestamp", -1).to_list(min(limit, 200))
