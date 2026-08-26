import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core.database import db
from core.security import GOVERNMENT_ROLES, REPORT_TYPES, SEVERITIES, VERIFY_ROLES, get_current_user
from core.ws import manager
from seed import _iso_mins_ago

router = APIRouter()

INCIDENT_CREATOR_ROLES = GOVERNMENT_ROLES | {"FIELD_OFFICER"}


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str
    title: str = Field(min_length=5, max_length=200)
    road_id: Optional[str] = None
    location: Optional[str] = None
    lat: float
    lng: float
    severity: str


@router.post("/incidents", status_code=201)
async def create_incident(body: IncidentCreate, user: dict = Depends(get_current_user)):
    """Government officials and field officers create incidents directly — broadcast to all roles immediately."""
    if user["role"] not in INCIDENT_CREATOR_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    itype = body.type.upper()
    severity = body.severity.upper()
    valid_types = REPORT_TYPES | {"TRAFFIC", "WEATHER", "UNKNOWN"}
    if itype not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid type. Valid: {sorted(valid_types)}")
    if severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Valid: {sorted(SEVERITIES)}")

    location = body.location
    if body.road_id:
        road = await db.roads.find_one({"id": body.road_id}, {"_id": 0})
        if road:
            location = road["name"]
    if not location:
        location = "Specified location"

    is_gov = user["role"] in GOVERNMENT_ROLES
    now_iso = datetime.now(timezone.utc).isoformat()
    incident = {
        "id": f"NER-{uuid.uuid4().hex[:5].upper()}",
        "type": itype,
        "severity": severity,
        "title": body.title,
        "location": location,
        "lat": body.lat,
        "lng": body.lng,
        "source": "GOVERNMENT" if is_gov else "FIELD",
        "confidence": 100 if is_gov else 90,
        "status": "VERIFIED",  # trusted roles broadcast immediately
        "created_at": now_iso,
        "verified_by": user["email"],
        "verified_at": now_iso,
    }
    await db.incidents.insert_one({**incident})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"], "official_email": user["email"], "official_name": user.get("name"),
        "action_type": "INCIDENT_CREATED", "target_type": "incident", "target_id": incident["id"],
        "target_name": body.title, "old_state": None, "new_state": "VERIFIED",
        "reason": f"Created by {'government official' if is_gov else 'field officer'}", "timestamp": now_iso,
    })
    await manager.broadcast({"type": "INCIDENT_CREATED", "id": incident["id"], "title": incident["title"], "severity": severity, "source": incident["source"]})
    incident.pop("_id", None)
    return incident


@router.patch("/incidents/{incident_id}/verify")
async def verify_incident(incident_id: str, user: dict = Depends(get_current_user)):
    if user["role"] not in VERIFY_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    if inc.get("status") == "VERIFIED":
        raise HTTPException(status_code=400, detail="Incident already verified")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.incidents.update_one({"id": incident_id}, {"$set": {"status": "VERIFIED", "verified_by": user["email"], "verified_at": now_iso}})
    if inc.get("field_report_id"):
        await db.field_reports.update_one({"id": inc["field_report_id"]}, {"$set": {"status": "VERIFIED"}})
    if inc.get("public_report_id"):
        await db.public_reports.update_one({"id": inc["public_report_id"]}, {"$set": {"status": "VERIFIED"}})
        rep = await db.public_reports.find_one({"id": inc["public_report_id"]})
        if rep:
            await db.users.update_one({"email": rep["reporter_email"]}, {"$inc": {"tokens": 10}})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"],
        "official_email": user["email"],
        "official_name": user.get("name"),
        "action_type": "INCIDENT_VERIFIED",
        "target_type": "incident",
        "target_id": incident_id,
        "target_name": inc.get("title"),
        "old_state": inc.get("status"),
        "new_state": "VERIFIED",
        "reason": "Government verification",
        "timestamp": now_iso,
    })
    await manager.broadcast({"type": "INCIDENT_VERIFIED", "id": incident_id, "title": inc.get("title")})
    return {"id": incident_id, "status": "VERIFIED"}


@router.patch("/incidents/{incident_id}/reject")
async def reject_incident(incident_id: str, user: dict = Depends(get_current_user)):
    if user["role"] not in VERIFY_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    inc = await db.incidents.find_one({"id": incident_id}, {"_id": 0})
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")
    if inc.get("status") in ("VERIFIED", "REJECTED"):
        raise HTTPException(status_code=400, detail=f"Incident already {inc['status'].lower()}")
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.incidents.update_one({"id": incident_id}, {"$set": {"status": "REJECTED", "rejected_by": user["email"], "rejected_at": now_iso}})
    if inc.get("field_report_id"):
        await db.field_reports.update_one({"id": inc["field_report_id"]}, {"$set": {"status": "REJECTED"}})
    if inc.get("public_report_id"):
        await db.public_reports.update_one({"id": inc["public_report_id"]}, {"$set": {"status": "REJECTED"}})
        rep = await db.public_reports.find_one({"id": inc["public_report_id"]})
        if rep:
            from datetime import timedelta
            ban_until = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
            await db.users.update_one({"email": rep["reporter_email"]}, {"$set": {"report_ban_until": ban_until}})
    await db.government_actions.insert_one({
        "id": str(uuid.uuid4()),
        "official_id": user["id"], "official_email": user["email"], "official_name": user.get("name"),
        "action_type": "INCIDENT_REJECTED", "target_type": "incident", "target_id": incident_id,
        "target_name": inc.get("title"), "old_state": inc.get("status"), "new_state": "REJECTED",
        "reason": "Rejected after review", "timestamp": now_iso,
    })
    await manager.broadcast({"type": "INCIDENT_REJECTED", "id": incident_id, "title": inc.get("title")})
    return {"id": incident_id, "status": "REJECTED"}


@router.get("/accidents")
async def list_accidents(user: dict = Depends(get_current_user)):
    """Verified accidents only — shown to public and logistics after field/gov verification."""
    incidents = await db.incidents.find(
        {"type": "ACCIDENT", "status": {"$in": ["VERIFIED", "PROVISIONALLY_BLOCKED"]}}, {"_id": 0}
    ).to_list(100)
    for i in incidents:
        if "created_at" not in i:
            i["created_at"] = _iso_mins_ago(i.get("created_minutes_ago", 0))
        i.pop("created_minutes_ago", None)
    incidents.sort(key=lambda x: x["created_at"], reverse=True)
    return incidents
