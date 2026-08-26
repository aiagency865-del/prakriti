import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core.database import db
from core.security import GOVERNMENT_ROLES, SEVERITIES, get_current_user
from core.ws import manager

router = APIRouter()


class NotificationCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=3, max_length=200)
    message: str = Field(min_length=5, max_length=1000)
    severity: str = "INFO"


@router.post("/notifications", status_code=201)
async def create_notification(body: NotificationCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in GOVERNMENT_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    severity = body.severity.upper()
    if severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Valid: {sorted(SEVERITIES)}")
    now_iso = datetime.now(timezone.utc).isoformat()
    notif = {
        "id": f"NT-{uuid.uuid4().hex[:6].upper()}",
        "title": body.title,
        "message": body.message,
        "severity": severity,
        "issued_by": user["email"],
        "issued_by_name": user.get("name"),
        "created_at": now_iso,
    }
    await db.notifications.insert_one({**notif})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"], "official_email": user["email"], "official_name": user.get("name"),
        "action_type": "NOTIFICATION_BROADCAST", "target_type": "all_users", "target_id": "all",
        "target_name": body.title, "old_state": None, "new_state": severity,
        "reason": body.message[:200], "timestamp": now_iso,
    })
    await manager.broadcast({"type": "NOTIFICATION", "id": notif["id"], "title": notif["title"], "severity": severity, "message": notif["message"]})
    notif.pop("_id", None)
    return notif


@router.get("/notifications")
async def list_notifications(user: dict = Depends(get_current_user)):
    return await db.notifications.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)


class EmergencyZoneCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    name: str = Field(min_length=3, max_length=200)
    lat: float
    lng: float
    radius_km: float = Field(gt=0.1, le=200)
    message: str = Field(min_length=5, max_length=1000)


@router.post("/emergency-zones", status_code=201)
async def create_emergency_zone(body: EmergencyZoneCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in GOVERNMENT_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    now_iso = datetime.now(timezone.utc).isoformat()
    zone = {
        "id": f"EZ-{uuid.uuid4().hex[:6].upper()}",
        "name": body.name,
        "lat": body.lat,
        "lng": body.lng,
        "radius_km": body.radius_km,
        "message": body.message,
        "active": True,
        "declared_by": user["email"],
        "declared_by_name": user.get("name"),
        "created_at": now_iso,
    }
    await db.emergency_zones.insert_one({**zone})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"], "official_email": user["email"], "official_name": user.get("name"),
        "action_type": "EMERGENCY_DECLARED", "target_type": "zone", "target_id": zone["id"],
        "target_name": body.name, "old_state": None, "new_state": f"{body.radius_km} km radius",
        "reason": body.message[:200], "timestamp": now_iso,
    })
    await manager.broadcast({"type": "EMERGENCY_DECLARED", "id": zone["id"], "name": zone["name"], "radius_km": zone["radius_km"], "message": zone["message"]})
    zone.pop("_id", None)
    return zone


@router.get("/emergency-zones")
async def list_emergency_zones(user: dict = Depends(get_current_user)):
    return await db.emergency_zones.find({"active": True}, {"_id": 0}).sort("created_at", -1).to_list(50)


@router.patch("/emergency-zones/{zone_id}/end")
async def end_emergency_zone(zone_id: str, user: dict = Depends(get_current_user)):
    if user["role"] not in GOVERNMENT_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    zone = await db.emergency_zones.find_one({"id": zone_id}, {"_id": 0})
    if not zone:
        raise HTTPException(status_code=404, detail="Emergency zone not found")
    if not zone.get("active"):
        raise HTTPException(status_code=400, detail="Emergency already ended")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.emergency_zones.update_one({"id": zone_id}, {"$set": {"active": False, "ended_by": user["email"], "ended_at": now_iso}})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"], "official_email": user["email"], "official_name": user.get("name"),
        "action_type": "EMERGENCY_ENDED", "target_type": "zone", "target_id": zone_id,
        "target_name": zone.get("name"), "old_state": "ACTIVE", "new_state": "ENDED",
        "reason": "Emergency lifted", "timestamp": now_iso,
    })
    await manager.broadcast({"type": "EMERGENCY_ENDED", "id": zone_id, "name": zone.get("name")})
    return {"id": zone_id, "active": False}
