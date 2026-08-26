import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core.database import db
from core.security import GOVERNMENT_ROLES, get_current_user
from core.ws import manager
from routers.routing import VEHICLE_SPEEDS

router = APIRouter()

VEHICLE_CREATOR_ROLES = GOVERNMENT_ROLES | {"FIELD_OFFICER", "LOGISTICS_OPERATOR"}


@router.get("/vehicles")
async def list_vehicles(user: dict = Depends(get_current_user)):
    return await db.vehicles.find({}, {"_id": 0}).to_list(500)


@router.get("/vehicles/{vehicle_id}")
async def get_vehicle(vehicle_id: str, user: dict = Depends(get_current_user)):
    v = await db.vehicles.find_one({"id": vehicle_id}, {"_id": 0})
    if not v:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    return v


class VehicleCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    number: str = Field(min_length=3, max_length=20)
    type: str
    lat: float
    lng: float
    destination: Optional[str] = None
    commodity: Optional[str] = None


@router.post("/vehicles", status_code=201)
async def create_vehicle(body: VehicleCreate, user: dict = Depends(get_current_user)):
    """Field officers (and government/logistics) can register vehicles on the network."""
    if user["role"] not in VEHICLE_CREATOR_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    vtype = body.type.upper()
    if vtype not in VEHICLE_SPEEDS:
        raise HTTPException(status_code=400, detail=f"Invalid type. Valid: {sorted(VEHICLE_SPEEDS.keys())}")
    number = body.number.strip().upper()
    if await db.vehicles.find_one({"number": number}):
        raise HTTPException(status_code=400, detail=f"Vehicle {number} already registered")
    now_iso = datetime.now(timezone.utc).isoformat()
    vehicle = {
        "id": f"veh-{uuid.uuid4().hex[:6]}",
        "number": number,
        "type": vtype,
        "lat": body.lat,
        "lng": body.lng,
        "heading": 0,
        "speed": 0,
        "status": "IDLE",
        "destination": body.destination or "—",
        "eta_minutes": None,
        "risk": 10,
        "commodity": body.commodity.upper() if body.commodity else None,
        "added_by": user["email"],
        "created_at": now_iso,
        "source": "FIELD" if user["role"] == "FIELD_OFFICER" else "GOVERNMENT",
    }
    await db.vehicles.insert_one({**vehicle})
    await manager.broadcast({"type": "VEHICLE_ADDED", "id": vehicle["id"], "number": number})
    vehicle.pop("_id", None)
    return vehicle
