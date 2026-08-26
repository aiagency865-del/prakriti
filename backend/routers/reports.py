import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core.database import db
from core.security import FIELD_ROLES, REPORT_TYPES, SEVERITIES, get_current_user
from core.ws import manager
from seed import _iso_mins_ago

router = APIRouter()


class FieldReportCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str
    description: str = Field(min_length=5, max_length=1000)
    road_id: Optional[str] = None
    lat: float
    lng: float
    severity: str


@router.post("/field/reports", status_code=201)
async def create_field_report(body: FieldReportCreate, user: dict = Depends(get_current_user)):
    if user["role"] not in FIELD_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    rtype = body.type.upper()
    severity = body.severity.upper()
    if rtype not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Valid: {sorted(REPORT_TYPES)}")
    if severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Valid: {sorted(SEVERITIES)}")

    location = "Field location"
    if body.road_id:
        road = await db.roads.find_one({"id": body.road_id}, {"_id": 0})
        if road:
            location = road["name"]

    now_iso = datetime.now(timezone.utc).isoformat()
    report = {
        "id": f"FR-{uuid.uuid4().hex[:6].upper()}",
        "officer_email": user["email"],
        "officer_name": user.get("name"),
        "type": rtype,
        "description": body.description,
        "road_id": body.road_id,
        "location": location,
        "lat": body.lat,
        "lng": body.lng,
        "severity": severity,
        "status": "SUBMITTED",
        "created_at": now_iso,
        "source": "FIELD",
    }
    await db.field_reports.insert_one({**report})

    # Propagate: a field report becomes an unverified incident visible to gov + logistics immediately
    incident = {
        "id": f"NER-{uuid.uuid4().hex[:5].upper()}",
        "type": rtype if rtype in ("LANDSLIDE", "FLOOD", "ROAD_DAMAGE", "BRIDGE_DAMAGE", "ACCIDENT") else "UNKNOWN",
        "severity": severity,
        "title": body.description[:80],
        "location": location,
        "lat": body.lat,
        "lng": body.lng,
        "source": "FIELD",
        "confidence": 60,
        "status": "UNVERIFIED",
        "created_at": now_iso,
        "source_tag": "FIELD_REPORT",
        "field_report_id": report["id"],
    }
    await db.incidents.insert_one({**incident})
    await manager.broadcast({"type": "FIELD_REPORT", "id": report["id"], "title": report["description"][:80], "severity": severity})
    report.pop("_id", None)
    return report


@router.get("/field/reports")
async def list_field_reports(user: dict = Depends(get_current_user)):
    q = {}
    if user["role"] in ("FIELD_OFFICER", "DRIVER"):
        q = {"officer_email": user["email"]}
    reports = await db.field_reports.find(q, {"_id": 0}).to_list(500)

    def key(r):
        return r.get("created_at") or _iso_mins_ago(r.get("created_minutes_ago", 0))
    reports.sort(key=key, reverse=True)
    for r in reports:
        if "created_at" not in r:
            r["created_at"] = _iso_mins_ago(r.get("created_minutes_ago", 0))
        r.pop("created_minutes_ago", None)
    return reports


class PublicReportCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    type: str
    description: str = Field(min_length=5, max_length=1000)
    road_id: Optional[str] = None
    lat: float
    lng: float
    severity: str = "INFO"


@router.post("/public/reports", status_code=201)
async def create_public_report(body: PublicReportCreate, user: dict = Depends(get_current_user)):
    ban = user.get("report_ban_until")
    if ban:
        try:
            ban_dt = datetime.fromisoformat(ban)
            if ban_dt.tzinfo is None:
                ban_dt = ban_dt.replace(tzinfo=timezone.utc)
            if ban_dt > datetime.now(timezone.utc):
                hours_left = round((ban_dt - datetime.now(timezone.utc)).total_seconds() / 3600, 1)
                raise HTTPException(status_code=403, detail=f"Reporting suspended for 24h after a rejected report. Try again in ~{hours_left}h.")
        except ValueError:
            pass
    rtype = body.type.upper()
    if rtype not in REPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid type. Valid: {sorted(REPORT_TYPES)}")
    severity = body.severity.upper() if body.severity else "INFO"
    if severity not in SEVERITIES:
        raise HTTPException(status_code=400, detail=f"Invalid severity. Valid: {sorted(SEVERITIES)}")

    location = "Reported location"
    if body.road_id:
        road = await db.roads.find_one({"id": body.road_id}, {"_id": 0})
        if road:
            location = road["name"]

    now_iso = datetime.now(timezone.utc).isoformat()
    report = {
        "id": f"PR-{uuid.uuid4().hex[:6].upper()}",
        "reporter_email": user["email"],
        "reporter_name": user.get("name"),
        "type": rtype,
        "description": body.description,
        "road_id": body.road_id,
        "location": location,
        "lat": body.lat,
        "lng": body.lng,
        "severity": severity,
        "status": "PENDING",  # becomes VERIFIED only after gov/field verification
        "created_at": now_iso,
        "source": "PUBLIC",
    }
    await db.public_reports.insert_one({**report})
    incident = {
        "id": f"NER-{uuid.uuid4().hex[:5].upper()}",
        "type": rtype if rtype in ("LANDSLIDE", "FLOOD", "ROAD_DAMAGE", "BRIDGE_DAMAGE", "ACCIDENT") else "UNKNOWN",
        "severity": severity,
        "title": body.description[:80],
        "location": location,
        "lat": body.lat,
        "lng": body.lng,
        "source": "PUBLIC",
        "confidence": 40,
        "status": "UNVERIFIED",
        "created_at": now_iso,
        "source_tag": "PUBLIC_REPORT",
        "public_report_id": report["id"],
    }
    await db.incidents.insert_one({**incident})
    await manager.broadcast({"type": "PUBLIC_REPORT", "id": report["id"], "title": report["description"][:80]})
    report.pop("_id", None)
    return report


@router.get("/public/reports")
async def list_my_public_reports(user: dict = Depends(get_current_user)):
    from core.security import GOVERNMENT_ROLES
    q = {} if user["role"] in GOVERNMENT_ROLES else {"reporter_email": user["email"]}
    reports = await db.public_reports.find(q, {"_id": 0}).sort("created_at", -1).to_list(200)
    return reports
