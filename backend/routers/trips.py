import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from core.database import db
from core.security import GOVERNMENT_ROLES, TRIPS_MONITOR_ROLES, get_current_user
from routers.routing import NER_PLACES, VEHICLE_SPEEDS, compute_route

router = APIRouter()


class TripCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    origin: str
    destination: str
    vehicle_type: str = "TRUCK"


@router.post("/trips", status_code=201)
async def start_trip(body: TripCreate, user: dict = Depends(get_current_user)):
    origin = body.origin.strip().lower()
    destination = body.destination.strip().lower()
    if origin not in NER_PLACES or destination not in NER_PLACES:
        raise HTTPException(status_code=400, detail=f"Unknown place. Valid: {sorted(NER_PLACES.keys())}")
    if origin == destination:
        raise HTTPException(status_code=400, detail="Origin and destination must be different")
    vehicle = body.vehicle_type.upper()
    if vehicle not in VEHICLE_SPEEDS:
        raise HTTPException(status_code=400, detail=f"Invalid vehicle type. Valid: {sorted(VEHICLE_SPEEDS.keys())}")
    route = await compute_route(origin, destination, vehicle)
    trip = {
        "id": f"TRIP-{uuid.uuid4().hex[:6].upper()}",
        "driver_email": user["email"],
        "driver_name": user.get("name"),
        "origin": origin,
        "destination": destination,
        "vehicle_type": vehicle,
        "status": "ACTIVE",
        "road_ids": route["recommended_route"].get("road_ids", []),
        "route": route,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.trips.insert_one({**trip})
    trip.pop("_id", None)
    return trip


@router.get("/trips")
async def list_trips(user: dict = Depends(get_current_user)):
    q = {} if user["role"] in GOVERNMENT_ROLES else {"driver_email": user["email"]}
    return await db.trips.find(q, {"_id": 0}).sort("created_at", -1).to_list(50)


@router.patch("/trips/{trip_id}/end")
async def end_trip(trip_id: str, user: dict = Depends(get_current_user)):
    trip = await db.trips.find_one({"id": trip_id}, {"_id": 0})
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    if trip["driver_email"] != user["email"] and user["role"] not in GOVERNMENT_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    await db.trips.update_one({"id": trip_id}, {"$set": {"status": "ENDED", "ended_at": datetime.now(timezone.utc).isoformat()}})
    return {"id": trip_id, "status": "ENDED"}


def _trip_live_position(trip, now):
    route = trip.get("route", {}).get("recommended_route", {})
    poly = route.get("polyline") or []
    eta = route.get("eta_minutes") or 60
    try:
        created_dt = datetime.fromisoformat(trip["created_at"])
        if created_dt.tzinfo is None:
            created_dt = created_dt.replace(tzinfo=timezone.utc)
        elapsed = (now - created_dt).total_seconds() / 60.0
    except Exception:
        elapsed = 0
    progress = min(0.95, max(0.0, elapsed / max(eta, 1)))
    if poly:
        idx = min(len(poly) - 1, int(progress * (len(poly) - 1)))
        lng, lat = poly[idx]
    else:
        lng, lat = NER_PLACES.get(trip["origin"], (0, 0))
    return progress, lat, lng


@router.get("/trips/summary")
async def trips_summary(user: dict = Depends(get_current_user)):
    """Live trip positions + per-corridor counts — government and field roles only."""
    if user["role"] not in TRIPS_MONITOR_ROLES:
        raise HTTPException(status_code=403, detail="You don't have permission for this action")
    trips = await db.trips.find({"status": "ACTIVE"}, {"_id": 0}).to_list(100)
    now = datetime.now(timezone.utc)
    by_road = {}
    out = []
    for t in trips:
        progress, lat, lng = _trip_live_position(t, now)
        out.append({
            "id": t["id"], "driver_name": t.get("driver_name"), "driver_email": t["driver_email"],
            "origin": t["origin"], "destination": t["destination"], "vehicle_type": t["vehicle_type"],
            "progress": round(progress, 2), "current_lat": lat, "current_lng": lng,
            "eta_minutes": t.get("route", {}).get("recommended_route", {}).get("eta_minutes"),
            "reroute_reason": t.get("reroute_reason"),
        })
        for rid in t.get("road_ids", []):
            by_road.setdefault(rid, {"count": 0, "vehicles": []})
            by_road[rid]["count"] += 1
            by_road[rid]["vehicles"].append(t["vehicle_type"])
    road_names = {r["id"]: r["name"] for r in await db.roads.find({}, {"_id": 0}).to_list(1000)}
    by_road_named = {rid: {"name": road_names.get(rid, rid), **v} for rid, v in by_road.items()}
    return {"active_count": len(trips), "by_road": by_road_named, "trips": out}
